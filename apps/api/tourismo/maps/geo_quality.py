"""Read-only source/coverage audit for public mapped places.

An editor can identify missing/uncertain coordinates without importing external
places, changing publication status, or exposing vendor/private documents.
"""
from collections import defaultdict
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import cast, func, select
from sqlalchemy.orm import Session, noload

from tourismo.admin.permissions import require_editor
from tourismo.core.database import get_db
from tourismo.core.models import (User, Destination, DestinationTranslation,
                                  PointOfInterest, PoiTranslation, ServiceListing, ContentSource)
from tourismo.listings.routes import _public_query
from tourismo.maps.routes import Geometry, safe_point

router = APIRouter(prefix='/api/v1/admin', tags=['geographic-quality'])
# These broad bounds are a *manual review hint*, not a legal country boundary.
SRI_LANKA_REVIEW_BOUNDS = (5.5, 79.4, 10.1, 82.1)


class GeoAuditRow(BaseModel):
    kind: Literal['destination', 'attraction', 'service']
    label: str
    detail_path: str
    district: str
    latitude: float | None = None
    longitude: float | None = None
    reason: Literal['missing_coordinates', 'missing_location_source',
                    'outside_sri_lanka_review_bounds', 'shared_coordinates_review']


class GeoAuditReport(BaseModel):
    scanned: int
    mapped: int
    sourced_mapped: int
    missing_coordinates: int
    missing_location_source: int
    outside_review_bounds: int
    shared_coordinate_groups: int
    issues: list[GeoAuditRow]
    issues_limited: bool
    scan_limited: bool
    note: str = ('Coordinate checks identify editorial review needs only; '
                 'they do not verify access, ownership, entrances or provider identity.')


def assess_geographic_quality(records: list[tuple[str, str, str, str, object, object, str | None]],
                              max_issues: int = 80, scan_limited: bool = False) -> GeoAuditReport:
    """Pure, testable logic; never auto-publishes or infers a missing coordinate."""
    issues = []
    mapped = sourced = missing = missing_source = outside = 0
    coordinate_groups = defaultdict(list)
    south, west, north, east = SRI_LANKA_REVIEW_BOUNDS

    def flag(item, reason):
        kind, label, path, district, latitude, longitude, _ = item
        if len(issues) < max_issues:
            issues.append(GeoAuditRow(kind=kind, label=label, detail_path=path,
                                      district=district,
                                      latitude=float(latitude) if safe_point(latitude, longitude) else None,
                                      longitude=float(longitude) if safe_point(latitude, longitude) else None,
                                      reason=reason))

    for item in records:
        kind, _, _, _, latitude, longitude, source = item
        if not safe_point(latitude, longitude):
            missing += 1
            flag(item, 'missing_coordinates')
            continue
        mapped += 1
        if not source or not source.startswith('https://'):
            missing_source += 1
            flag(item, 'missing_location_source')
        else:
            sourced += 1
        if not (south <= float(latitude) <= north and west <= float(longitude) <= east):
            outside += 1
            flag(item, 'outside_sri_lanka_review_bounds')
        # Shared points can be completely legitimate (several services in one
        # hotel): signal review only, never remove or move an existing marker.
        coordinate_groups[(round(float(latitude), 5), round(float(longitude), 5))].append(item)

    shared_groups = [members for members in coordinate_groups.values() if len(members) > 1]
    for members in shared_groups:
        for member in members:
            flag(member, 'shared_coordinates_review')
    total_flags = missing + missing_source + outside + sum(map(len, shared_groups))
    return GeoAuditReport(scanned=len(records), mapped=mapped, sourced_mapped=sourced,
                          missing_coordinates=missing, missing_location_source=missing_source,
                          outside_review_bounds=outside, shared_coordinate_groups=len(shared_groups),
                          issues=issues, issues_limited=total_flags > len(issues), scan_limited=scan_limited)


@router.get('/geo-quality', response_model=GeoAuditReport)
def admin_geographic_quality(
    max_issues: int = Query(default=80, ge=1, le=100),
    editor: User = Depends(require_editor), db: Session = Depends(get_db),
):
    """Editorial coverage check. Maximum 5,001 rows to bound memory usage."""
    cap = 5001
    records = []
    lat = func.ST_Y(cast(Destination.location, Geometry()))
    lon = func.ST_X(cast(Destination.location, Geometry()))
    destinations = (select(Destination.slug, DestinationTranslation.title, Destination.district,
                           lat, lon, Destination.location_source_url)
                    .join(DestinationTranslation, DestinationTranslation.destination_id == Destination.id)
                    .where(DestinationTranslation.locale == 'en',
                           Destination.content_status.in_(['sample', 'published']))
                    .order_by(Destination.slug).limit(cap))
    for slug, title, district, latitude, longitude, source in db.execute(destinations).all():
        records.append(('destination', title, f'/destinations/{slug}', district,
                        latitude, longitude, source))
    if len(records) < cap:
        pois = (select(PointOfInterest.slug, PoiTranslation.title, Destination.slug, Destination.district,
                       PointOfInterest.latitude, PointOfInterest.longitude,
                       func.coalesce(PointOfInterest.location_source_url, ContentSource.url))
                .outerjoin(ContentSource, PointOfInterest.source_id == ContentSource.id)
                .join(Destination, PointOfInterest.destination_id == Destination.id)
                .join(PoiTranslation, PoiTranslation.poi_id == PointOfInterest.id)
                .where(PoiTranslation.locale == 'en',
                       PointOfInterest.content_status.in_(['sample', 'published']),
                       Destination.content_status.in_(['sample', 'published']))
                .order_by(Destination.slug, PointOfInterest.slug).limit(cap-len(records)))
        for _, title, slug, district, latitude, longitude, source in db.execute(pois).all():
            records.append(('attraction', title, f'/destinations/{slug}', district,
                            latitude, longitude, source))
    if len(records) < cap:
        # Use the same publication/verification eligibility gate as public map.
        published = (_public_query()
                     .options(noload(ServiceListing.photos), noload(ServiceListing.revisions))
                     .order_by(ServiceListing.id.asc()).limit(cap-len(records)))
        for row in db.scalars(published).all():
            records.append(('service', row.title, f'/listings/{row.slug}', row.district,
                            row.latitude, row.longitude, row.location_source_url))
    scan_limited = len(records) >= cap
    return assess_geographic_quality(records, max_issues, scan_limited)
