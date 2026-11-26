"""Consent-based directions: sourced points and optional licensed route estimates.

No user coordinates are persisted. External routing is disabled unless a server-side
API key is supplied; we never invent road kilometers, transit times, or schedules.
"""
from datetime import datetime, timezone
from math import asin, cos, isfinite, radians, sin, sqrt
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import cast, func, select
from sqlalchemy.orm import Session

from tourismo.core.config import get_settings
from tourismo.core.database import get_db
from tourismo.core.models import Destination, ServiceListing
from tourismo.listings.routes import _public_query
from tourismo.maps.routes import Geometry, safe_point

router = APIRouter(prefix='/api/v1/navigation', tags=['travel-directions'])
Mode = Literal['driving', 'walking', 'transit', 'bicycling']
Kind = Literal['destination', 'service']


class Point(BaseModel):
    kind: Kind
    slug: str
    title: str
    latitude: float
    longitude: float
    accuracy_note: str
    source_url: str | None
    is_sample: bool = False


class RouteRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kind: Kind
    slug: str = Field(min_length=1, max_length=150, pattern=r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
    origin_latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    origin_longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    mode: Mode


def straight_line_km(a_lat: float, a_lon: float, b_lat: float, b_lon: float) -> float:
    """Great-circle km, never a route/driving distance."""
    lat1, lat2 = radians(a_lat), radians(b_lat)
    d_lat, d_lon = lat2 - lat1, radians(b_lon - a_lon)
    h = sin(d_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(d_lon / 2) ** 2
    return 6371.0088 * 2 * asin(min(1, sqrt(h)))


def get_target(db: Session, kind: Kind, slug: str) -> Point:
    if kind == 'service':
        listing = db.scalar(_public_query().where(ServiceListing.slug == slug))
        if not listing:
            raise HTTPException(404, 'Published service not found')
        latitude, longitude = listing.latitude, listing.longitude
        if not safe_point(latitude, longitude):
            raise HTTPException(404, 'A location has not been supplied for this service')
        return Point(kind=kind, slug=slug, title=listing.title,
                     latitude=float(latitude), longitude=float(longitude),
                     accuracy_note=listing.location_note or 'Provider reference point; visitor entrance not verified.',
                     source_url=listing.location_source_url)

    latitude = func.ST_Y(cast(Destination.location, Geometry()))
    longitude = func.ST_X(cast(Destination.location, Geometry()))
    row = db.execute(select(Destination, latitude, longitude).where(
        Destination.slug == slug,
        Destination.content_status.in_(['published', 'sample']),
        Destination.location.is_not(None))).first()
    if row is None or not safe_point(row[1], row[2]):
        raise HTTPException(404, 'A sourced destination location is not available')
    place = row[0]
    title = next((t.title for t in place.translations if t.locale == 'en'), slug.replace('-', ' ').title())
    return Point(kind=kind, slug=slug, title=title,
                 latitude=float(row[1]), longitude=float(row[2]),
                 accuracy_note='Destination reference point; not a verified arrival entrance.',
                 source_url=place.location_source_url, is_sample=place.content_status == 'sample')


@router.get('/targets/{kind}/{slug}', response_model=Point)
def target(kind: Kind, slug: str, db: Session = Depends(get_db)):
    return get_target(db, kind, slug)


def google_route(origin_lat: float, origin_lon: float, target: Point, mode: Mode) -> tuple[float, int] | None:
    """Call Google Routes only with explicit user consent and configured billing.

    Response contains summary only; Google route polylines are NOT placed on OSM tiles.
    """
    settings = get_settings()
    if not settings.google_routes_api_key:
        return None
    modes = {'driving': 'DRIVE', 'walking': 'WALK', 'bicycling': 'BICYCLE', 'transit': 'TRANSIT'}
    payload = {
        'origin': {'location': {'latLng': {'latitude': origin_lat, 'longitude': origin_lon}}},
        'destination': {'location': {'latLng': {'latitude': target.latitude, 'longitude': target.longitude}}},
        'travelMode': modes[mode],
        'computeAlternativeRoutes': False,
        'languageCode': 'en',
        'units': 'METRIC',
    }
    try:
        response = httpx.post('https://routes.googleapis.com/directions/v2:computeRoutes',
            json=payload, headers={
                'X-Goog-Api-Key': settings.google_routes_api_key,
                'X-Goog-FieldMask': 'routes.duration,routes.distanceMeters',
            }, timeout=8.0)
        response.raise_for_status()
        route = (response.json().get('routes') or [None])[0]
        if not isinstance(route, dict):
            return None
        distance = route.get('distanceMeters')
        duration = route.get('duration')
        if not isinstance(distance, (int, float)) or distance < 0 or not isinstance(duration, str) or not duration.endswith('s'):
            return None
        seconds = float(duration[:-1])
        if not isfinite(seconds) or seconds < 0:
            return None
        return (round(distance / 1000, 1), round(seconds / 60))
    except (httpx.HTTPError, ValueError, TypeError, KeyError):
        # No misleading fallback road time, and never log precise user coordinates.
        return None


@router.post('/estimate')
def estimate(body: RouteRequest, response: Response, db: Session = Depends(get_db)):
    response.headers['Cache-Control'] = 'no-store'
    point = get_target(db, body.kind, body.slug)
    direct = round(straight_line_km(body.origin_latitude, body.origin_longitude, point.latitude, point.longitude), 1)
    route = google_route(body.origin_latitude, body.origin_longitude, point, body.mode)
    configured = bool(get_settings().google_routes_api_key)
    return {
        'destination': point.model_dump(), 'straight_line_km': direct,
        'mode': body.mode, 'road_distance_km': route[0] if route else None,
        'estimated_minutes': route[1] if route else None,
        'estimate_source': 'Google Routes API' if route else None,
        'estimate_status': 'available' if route else ('no_route_returned' if configured else 'provider_not_configured'),
        'checked_at': datetime.now(timezone.utc).isoformat(),
        'disclaimer': 'Estimates are not live guarantees. Confirm opening times, boarding points, fares and local access.',
    }
