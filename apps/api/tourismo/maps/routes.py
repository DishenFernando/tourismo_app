"""Tourismo Phase 5.1: public, verified-source map points.

This endpoint is read-only. It never leaks vendor applications, documents, draft
POIs, or unpublished listing revisions. Absence of coordinates means no marker.
"""
from math import isfinite
from collections import defaultdict
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import cast, func, select, or_
from sqlalchemy.types import UserDefinedType
from sqlalchemy.orm import Session, joinedload, noload

from tourismo.core.config import get_settings
from tourismo.core.database import get_db
from tourismo.core.geo import Geography
from tourismo.core.models import (Destination, DestinationTranslation, PointOfInterest,
                                  PoiTranslation, ServiceListing, User)
from tourismo.listings.routes import _public_query
from tourismo.identity.security import require_user
from tourismo.maps.location_links import LocationLinkInput, ResolvedLocation, resolve_location_link
from tourismo.maps.place_ids import parse_place_id

router = APIRouter(prefix='/api/v1/map', tags=['geographic-discovery'])


@router.post('/resolve-location', response_model=ResolvedLocation)
def resolve_shared_map_location(body: LocationLinkInput, user: User = Depends(require_user)):
    """An authenticated editor/vendor resolves a shared link before selecting it."""
    return resolve_location_link(body.url)


class Geometry(UserDefinedType):
    """Allow PostGIS geography to be read as geometry without geoalchemy2."""
    cache_ok = True

    def get_col_spec(self, **kw):
        return 'geometry'


class MapPoint(BaseModel):
    id: str
    kind: Literal['destination', 'attraction', 'service']
    title: str
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    category: str
    district: str
    detail_path: str
    is_sample: bool = False
    business_verified: bool = False
    location_note: str
    source_url: str | None = None


def safe_point(latitude, longitude) -> bool:
    """Never produce invalid coordinates or artificial (0, 0) fallback pins."""
    if latitude is None or longitude is None:
        return False
    try:
        lat, lon = float(latitude), float(longitude)
    except (TypeError, ValueError):
        return False
    return isfinite(lat) and isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180


def valid_bbox(south: float, west: float, north: float, east: float) -> None:
    if south >= north or west >= east:
        raise HTTPException(422, 'Map bounds must satisfy south < north and west < east')
    if north - south > 20 or east - west > 20:
        raise HTTPException(422, 'Zoom in to an area no larger than 20 degrees per axis')


def _map_points(db: Session, south: float, west: float, north: float, east: float,
                kind: Literal['all', 'destination', 'attraction', 'service'],
                cap_per_kind: int | None = None) -> list[MapPoint]:
    results: list[MapPoint] = []
    if kind in ('all', 'destination'):
        # Destination pins exist only where the editorial record has an actual
        # PostGIS point. Many directory-only destinations do not yet have one.
        lat = func.ST_Y(cast(Destination.location, Geometry())).label('latitude')
        lon = func.ST_X(cast(Destination.location, Geometry())).label('longitude')
        stmt = (select(Destination, DestinationTranslation.title, lat, lon)
                .join(DestinationTranslation, DestinationTranslation.destination_id == Destination.id)
                .where(DestinationTranslation.locale == 'en',
                       Destination.content_status.in_(['sample', 'published']),
                       Destination.location.is_not(None),
                       lat.between(south, north), lon.between(west, east))
                .options(noload(Destination.translations), noload(Destination.photos))
                .order_by(Destination.slug).limit(cap_per_kind or 150))
        for place, title, latitude, longitude in db.execute(stmt).all():
            if safe_point(latitude, longitude):
                results.append(MapPoint(
                    id=f'destination:{place.id}', kind='destination', title=title,
                    latitude=latitude, longitude=longitude, category='destination',
                    district=place.district, detail_path=f'/destinations/{place.slug}',
                    is_sample=place.content_status == 'sample',
                    location_note='Approximate editorial reference point; not a verified entrance.',
                    source_url=place.location_source_url))

    if kind in ('all', 'attraction'):
        stmt = (select(PointOfInterest, PoiTranslation.title, Destination.slug, Destination.district)
                .join(Destination, PointOfInterest.destination_id == Destination.id)
                .join(PoiTranslation, PoiTranslation.poi_id == PointOfInterest.id)
                .where(PoiTranslation.locale == 'en',
                       PointOfInterest.content_status.in_(['sample', 'published']),
                       Destination.content_status.in_(['sample', 'published']),
                       PointOfInterest.latitude.is_not(None), PointOfInterest.longitude.is_not(None),
                       PointOfInterest.latitude.between(south, north),
                       PointOfInterest.longitude.between(west, east))
                .options(joinedload(PointOfInterest.source))
                .order_by(Destination.slug, PointOfInterest.slug).limit(cap_per_kind or 200))
        for poi, title, destination_slug, district in db.execute(stmt).all():
            if safe_point(poi.latitude, poi.longitude):
                results.append(MapPoint(
                    id=f'attraction:{poi.id}', kind='attraction', title=title,
                    latitude=poi.latitude, longitude=poi.longitude,
                    category=poi.category, district=district,
                    detail_path=f'/destinations/{destination_slug}',
                    is_sample=poi.content_status == 'sample',
                    location_note='Approximate attraction reference point; not a confirmed entrance or route.',
                    source_url=poi.location_source_url or (poi.source.url if poi.source else None)))

    if kind in ('all', 'service'):
        # Same gate as /api/v1/listings: independently published AND business
        # not rejected/expired (including any expired verification evidence).
        stmt = (_public_query()
                .where(ServiceListing.latitude.is_not(None), ServiceListing.longitude.is_not(None),
                       ServiceListing.latitude.between(south, north),
                       ServiceListing.longitude.between(west, east))
                .options(noload(ServiceListing.photos), noload(ServiceListing.revisions))
                .order_by(ServiceListing.published_at.desc(), ServiceListing.id.asc())
                .limit(cap_per_kind or 200))
        for listing in db.scalars(stmt).all():
            if safe_point(listing.latitude, listing.longitude):
                results.append(MapPoint(
                    id=f'service:{listing.id}', kind='service', title=listing.title,
                    latitude=listing.latitude, longitude=listing.longitude,
                    category=listing.category, district=listing.district,
                    detail_path=f'/listings/{listing.slug}', is_sample=False,
                    business_verified=listing.organization.verification_state == 'approved',
                    location_note=(listing.location_note or
                                   'Provider-supplied approximate location; independently confirm access.'),
                    source_url=listing.location_source_url))
    return results


@router.get('/points', response_model=list[MapPoint])
def public_map_points(
    kind: Literal['all', 'destination', 'attraction', 'service'] = 'all',
    south: float = Query(default=5.5, ge=-90, le=90, allow_inf_nan=False),
    west: float = Query(default=79.4, ge=-180, le=180, allow_inf_nan=False),
    north: float = Query(default=10.1, ge=-90, le=90, allow_inf_nan=False),
    east: float = Query(default=82.1, ge=-180, le=180, allow_inf_nan=False),
    db: Session = Depends(get_db),
):
    valid_bbox(south, west, north, east)
    return _map_points(db, south, west, north, east, kind)


class ViewportResponse(BaseModel):
    """A bounded snapshot of visible *public* pins; zoom in when truncated."""
    points: list[MapPoint]
    has_more: bool
    limit: int


def _balanced_viewport(points: list[MapPoint], limit: int) -> ViewportResponse:
    """Round-robin categories so a dense single category cannot hide others.

    The query fetches `limit + 1` for each kind. Thus a returned `has_more`
    is never silently false because a per-kind SQL cap was reached.
    """
    groups = {kind: [] for kind in ('destination', 'attraction', 'service')}
    for point in points:
        groups[point.kind].append(point)
    ordered: list[MapPoint] = []
    for index in range(max((len(group) for group in groups.values()), default=0)):
        for group in groups.values():
            if index < len(group):
                ordered.append(group[index])
                if len(ordered) > limit:
                    return ViewportResponse(points=ordered[:limit], has_more=True, limit=limit)
    return ViewportResponse(points=ordered, has_more=False, limit=limit)


@router.get('/viewport', response_model=ViewportResponse)
def public_map_viewport(
    kind: Literal['all', 'destination', 'attraction', 'service'] = 'all',
    south: float = Query(default=5.5, ge=-90, le=90, allow_inf_nan=False),
    west: float = Query(default=79.4, ge=-180, le=180, allow_inf_nan=False),
    north: float = Query(default=10.1, ge=-90, le=90, allow_inf_nan=False),
    east: float = Query(default=82.1, ge=-180, le=180, allow_inf_nan=False),
    limit: int = Query(default=180, ge=20, le=250),
    db: Session = Depends(get_db),
):
    """Only public, sourced-position records inside the requested map view.

    A hard server limit prevents a zoomed-out map from sending thousands of
    markers to a mobile client. `has_more` means zoom in; no fake clusters or
    private unpublished provider records are returned. The legacy /points
    array endpoint remains unchanged for Phase 5.1-5.3 callers.
    """
    valid_bbox(south, west, north, east)
    return _balanced_viewport(
        _map_points(db, south, west, north, east, kind, cap_per_kind=limit + 1), limit)


class ItineraryPlacesRequest(BaseModel):
    """Resolve only currently public points; accept bounded, canonical IDs."""
    place_ids: list[str] = Field(min_length=1, max_length=90)


def _itinerary_public_places(db: Session, place_ids: list[str]) -> list[MapPoint]:
    by_kind: dict[str, set] = defaultdict(set)
    for value in place_ids:
        kind, public_id = parse_place_id(value)
        by_kind[kind].add(public_id)

    found: dict[str, MapPoint] = {}
    if by_kind['destination']:
        lat = func.ST_Y(cast(Destination.location, Geometry())).label('latitude')
        lon = func.ST_X(cast(Destination.location, Geometry())).label('longitude')
        stmt = (select(Destination, DestinationTranslation.title, lat, lon)
                .join(DestinationTranslation, DestinationTranslation.destination_id == Destination.id)
                .where(Destination.id.in_(by_kind['destination']), DestinationTranslation.locale == 'en',
                       Destination.content_status.in_(['sample', 'published']), Destination.location.is_not(None)))
        for row, title, latitude, longitude in db.execute(stmt).all():
            if safe_point(latitude, longitude):
                point = MapPoint(id=f'destination:{row.id}', kind='destination', title=title,
                                 latitude=latitude, longitude=longitude, category='destination',
                                 district=row.district, detail_path=f'/destinations/{row.slug}',
                                 is_sample=row.content_status == 'sample',
                                 location_note='Approximate editorial reference point; not a verified entrance.',
                                 source_url=row.location_source_url)
                found[point.id] = point

    if by_kind['attraction']:
        stmt = (select(PointOfInterest, PoiTranslation.title, Destination.slug, Destination.district)
                .join(Destination, PointOfInterest.destination_id == Destination.id)
                .join(PoiTranslation, PoiTranslation.poi_id == PointOfInterest.id)
                .where(PointOfInterest.id.in_(by_kind['attraction']), PoiTranslation.locale == 'en',
                       PointOfInterest.content_status.in_(['sample', 'published']),
                       Destination.content_status.in_(['sample', 'published']),
                       PointOfInterest.latitude.is_not(None), PointOfInterest.longitude.is_not(None)))
        for row, title, destination_slug, district in db.execute(stmt).all():
            if safe_point(row.latitude, row.longitude):
                point = MapPoint(id=f'attraction:{row.id}', kind='attraction', title=title,
                                 latitude=row.latitude, longitude=row.longitude, category=row.category,
                                 district=district, detail_path=f'/destinations/{destination_slug}',
                                 is_sample=row.content_status == 'sample',
                                 location_note='Approximate attraction reference point; not a confirmed entrance or route.',
                                 source_url=row.location_source_url or (row.source.url if row.source else None))
                found[point.id] = point

    if by_kind['service']:
        stmt = _public_query().where(ServiceListing.id.in_(by_kind['service']),
                                     ServiceListing.latitude.is_not(None),
                                     ServiceListing.longitude.is_not(None))
        for row in db.scalars(stmt).all():
            if safe_point(row.latitude, row.longitude):
                point = MapPoint(id=f'service:{row.id}', kind='service', title=row.title,
                                 latitude=row.latitude, longitude=row.longitude, category=row.category,
                                 district=row.district, detail_path=f'/listings/{row.slug}',
                                 business_verified=row.organization.verification_state == 'approved',
                                 location_note=row.location_note or 'Provider-supplied approximate location.',
                                 source_url=row.location_source_url)
                found[point.id] = point

    # Preserve user's itinerary order, omit unavailable/rejected/archived points.
    return [found[value] for value in dict.fromkeys(place_ids) if value in found]


@router.post('/itinerary-places', response_model=list[MapPoint])
def resolve_itinerary_places(body: ItineraryPlacesRequest, db: Session = Depends(get_db)):
    try:
        return _itinerary_public_places(db, body.place_ids)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get('/config')
def public_map_config():
    """Never expose a server-only secret as a browser tile token."""
    settings = get_settings()
    tile_url = settings.map_tile_url.strip()
    if not tile_url and settings.app_environment != 'production':
        tile_url = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
    if tile_url and (not tile_url.startswith('https://') or
                     any(value not in tile_url for value in ('{z}', '{x}', '{y}'))):
        tile_url = ''
    return {'tile_url': tile_url or None,
            'attribution': settings.map_tile_attribution,
            'demo_mode': settings.app_environment == 'development' and settings.enable_demo_catalog}


# Phase 5.2: one bounded, public geographic discovery contract for all place types.
# The radius is in meters as PostGIS geography, not latitude/longitude degrees.
class NearbyPoint(MapPoint):
    distance_km: float = Field(ge=0, allow_inf_nan=False)


class NearbyCenter(BaseModel):
    title: str
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    kind: Literal['destination', 'selected_location']
    destination_slug: str | None = None


class NearbyResponse(BaseModel):
    center: NearbyCenter
    radius_km: float
    points: list[NearbyPoint]
    has_more: bool
    distance_note: str = 'Distances are straight-line estimates, not routes or travel times.'


def _geography_point(latitude, longitude):
    # Input longitude is first for ST_MakePoint (X, Y).
    return cast(func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326), Geography())


def _nearby_center(db: Session, destination: str | None,
                   near_lat: float | None, near_lon: float | None) -> NearbyCenter:
    if destination and (near_lat is not None or near_lon is not None):
        raise HTTPException(422, 'Choose a destination or coordinates, not both')
    if not destination and (near_lat is None or near_lon is None):
        raise HTTPException(422, 'Choose a mapped destination or supply both coordinates')
    if destination:
        lat = func.ST_Y(cast(Destination.location, Geometry()))
        lon = func.ST_X(cast(Destination.location, Geometry()))
        result = db.execute(
            select(Destination, DestinationTranslation.title, lat, lon)
            .join(DestinationTranslation, DestinationTranslation.destination_id == Destination.id)
            .where(Destination.slug == destination,
                   Destination.content_status.in_(['sample', 'published']),
                   DestinationTranslation.locale == 'en')
        ).first()
        if result is None:
            raise HTTPException(404, 'Public destination not found')
        place, title, latitude, longitude = result
        if not safe_point(latitude, longitude):
            raise HTTPException(422, 'This destination has no recorded map coordinates. Choose a mapped place instead.')
        return NearbyCenter(title=title, latitude=float(latitude), longitude=float(longitude),
                            kind='destination', destination_slug=place.slug)
    if not safe_point(near_lat, near_lon):
        raise HTTPException(422, 'Invalid map center coordinates')
    return NearbyCenter(title='Selected map location', latitude=near_lat, longitude=near_lon,
                        kind='selected_location')


def _nearby_points(db: Session, center: NearbyCenter, radius_km: float,
                   kind: Literal['all', 'destination', 'attraction', 'service'],
                   category: str | None, q: str, limit: int) -> NearbyResponse:
    origin = _geography_point(center.latitude, center.longitude)
    radius_m = radius_km * 1000
    cap = limit + (2 if center.destination_slug else 1)  # include one spare when the origin itself is excluded.
    results: list[NearbyPoint] = []
    term = f'%{q.strip()}%' if q.strip() else None

    if kind in ('all', 'destination') and (category is None or category == 'destination'):
        latitude = func.ST_Y(cast(Destination.location, Geometry()))
        longitude = func.ST_X(cast(Destination.location, Geometry()))
        distance = func.ST_Distance(Destination.location, origin)
        stmt = (select(Destination, DestinationTranslation.title, latitude, longitude, distance)
                .join(DestinationTranslation, DestinationTranslation.destination_id == Destination.id)
                .where(DestinationTranslation.locale == 'en',
                       Destination.content_status.in_(['sample', 'published']),
                       Destination.location.is_not(None),
                       func.ST_DWithin(Destination.location, origin, radius_m)))
        if term:
            stmt = stmt.where(or_(DestinationTranslation.title.ilike(term), Destination.district.ilike(term)))
        stmt = stmt.order_by(distance.asc(), Destination.id.asc()).limit(cap)
        for place, title, lat, lon, meters in db.execute(stmt).all():
            if not safe_point(lat, lon) or meters is None or float(meters) < 0:
                continue
            # Don't suggest the selected destination as a nearby destination.
            if center.destination_slug == place.slug:
                continue
            results.append(NearbyPoint(
                id=f'destination:{place.id}', kind='destination', title=title,
                latitude=lat, longitude=lon, category='destination', district=place.district,
                detail_path=f'/destinations/{place.slug}', is_sample=place.content_status == 'sample',
                business_verified=False, location_note='Approximate editorial reference point; not a verified entrance.',
                source_url=place.location_source_url, distance_km=round(float(meters) / 1000, 2)))

    if kind in ('all', 'attraction'):
        point = _geography_point(PointOfInterest.latitude, PointOfInterest.longitude)
        distance = func.ST_Distance(point, origin)
        stmt = (select(PointOfInterest, PoiTranslation.title, Destination.slug, Destination.district, distance)
                .join(Destination, PointOfInterest.destination_id == Destination.id)
                .join(PoiTranslation, PoiTranslation.poi_id == PointOfInterest.id)
                .where(PoiTranslation.locale == 'en',
                       Destination.content_status.in_(['sample', 'published']),
                       PointOfInterest.content_status.in_(['sample', 'published']),
                       PointOfInterest.latitude.is_not(None), PointOfInterest.longitude.is_not(None),
                       PointOfInterest.latitude.between(-90, 90),
                       PointOfInterest.longitude.between(-180, 180),
                       func.ST_DWithin(point, origin, radius_m)))
        if category:
            stmt = stmt.where(PointOfInterest.category == category)
        if term:
            stmt = stmt.where(or_(PoiTranslation.title.ilike(term), Destination.district.ilike(term)))
        stmt = stmt.order_by(distance.asc(), PointOfInterest.id.asc()).limit(cap)
        for poi, title, destination_slug, district, meters in db.execute(stmt).all():
            if not safe_point(poi.latitude, poi.longitude) or meters is None or float(meters) < 0:
                continue
            results.append(NearbyPoint(
                id=f'attraction:{poi.id}', kind='attraction', title=title,
                latitude=poi.latitude, longitude=poi.longitude, category=poi.category,
                district=district, detail_path=f'/destinations/{destination_slug}',
                is_sample=poi.content_status == 'sample', business_verified=False,
                location_note='Approximate attraction reference point; check access and opening hours.',
                source_url=poi.location_source_url or (poi.source.url if poi.source else None),
                distance_km=round(float(meters) / 1000, 2)))

    if kind in ('all', 'service'):
        point = _geography_point(ServiceListing.latitude, ServiceListing.longitude)
        distance = func.ST_Distance(point, origin)
        # This is intentionally the same publication/expiry gate as /listings and /map/points.
        stmt = (_public_query()
                .where(ServiceListing.latitude.is_not(None), ServiceListing.longitude.is_not(None),
                       ServiceListing.latitude.between(-90, 90),
                       ServiceListing.longitude.between(-180, 180),
                       func.ST_DWithin(point, origin, radius_m)))
        if category:
            stmt = stmt.where(ServiceListing.category == category)
        if term:
            stmt = stmt.where(or_(ServiceListing.title.ilike(term),
                                  ServiceListing.summary.ilike(term),
                                  ServiceListing.district.ilike(term)))
        stmt = stmt.add_columns(distance.label('distance_m')).order_by(distance.asc(), ServiceListing.id.asc()).limit(cap)
        for listing, meters in db.execute(stmt).all():
            if not safe_point(listing.latitude, listing.longitude) or meters is None or float(meters) < 0:
                continue
            results.append(NearbyPoint(
                id=f'service:{listing.id}', kind='service', title=listing.title,
                latitude=listing.latitude, longitude=listing.longitude,
                category=listing.category, district=listing.district,
                detail_path=f'/listings/{listing.slug}', is_sample=False,
                business_verified=listing.organization.verification_state == 'approved',
                location_note=listing.location_note or 'Provider-supplied point; confirm the actual entrance.',
                source_url=listing.location_source_url,
                distance_km=round(float(meters) / 1000, 2)))

    results.sort(key=lambda p: (p.distance_km, p.id))
    return NearbyResponse(center=center, radius_km=radius_km,
                          points=results[:limit], has_more=len(results) > limit)


@router.get('/nearby', response_model=NearbyResponse)
def nearby_places(
    destination: str | None = Query(default=None, max_length=120, pattern=r'^[a-z0-9-]+$'),
    near_lat: float | None = Query(default=None, ge=-90, le=90, allow_inf_nan=False),
    near_lon: float | None = Query(default=None, ge=-180, le=180, allow_inf_nan=False),
    radius_km: float = Query(default=25, gt=0, le=100, allow_inf_nan=False),
    kind: Literal['all', 'destination', 'attraction', 'service'] = 'all',
    category: str | None = Query(default=None, max_length=40, pattern=r'^[a-z_]+$'),
    q: str = Query(default='', max_length=80),
    limit: int = Query(default=60, ge=1, le=60),
    db: Session = Depends(get_db),
):
    center = _nearby_center(db, destination, near_lat, near_lon)
    return _nearby_points(db, center, radius_km, kind, category, q, limit)
