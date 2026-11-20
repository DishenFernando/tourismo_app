"""Phase 4.1: structured discovery-only tourism listings.

Public routes expose ONLY published listings from currently approved organizations.
Private organization details, license evidence and draft content never leave privileged routes.
"""
import re
import uuid
from datetime import date
from typing import Any, Literal
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, ValidationError, field_validator, model_validator, ValidationInfo
from sqlalchemy import Integer, and_, cast, exists, func, literal, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import JSONB

from tourismo.admin.permissions import require_admin
from tourismo.core.database import get_db
from tourismo.core.geo import Geography
from tourismo.core.models import (
    Destination, AuditEvent, ServiceListing, ServiceListingPhoto, ServiceListingReview, ServiceListingRevision, User,
    VendorEvidence, VendorMembership, VendorOrganization, now_utc,
)
from tourismo.identity.security import require_privileged_mfa, require_user
from tourismo.vendors.routes import _organization

public_router = APIRouter(prefix='/api/v1/listings', tags=['public-listings'])
vendor_router = APIRouter(prefix='/api/v1/vendor', tags=['vendor-listings'])
admin_router = APIRouter(prefix='/api/v1/admin/listings', tags=['listing-moderation'])
Category = Literal['accommodation', 'restaurant', 'guide', 'transport', 'tour_operator', 'activity']


class RoomType(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=2, max_length=100)
    max_adults: int = Field(ge=1, le=30)
    max_children: int = Field(ge=0, le=30)
    number_of_rooms: int = Field(ge=1, le=2000)
    indicative_nightly_lkr_minor: int | None = Field(default=None, ge=0, le=100_000_000)
    min_child_age: int | None = Field(default=None, ge=0, le=17)
    max_child_age: int | None = Field(default=None, ge=0, le=17)
    max_total_guests: int | None = Field(default=None, ge=1, le=60)

    @model_validator(mode='after')
    def age_limits(self):
        if self.min_child_age is not None and self.max_child_age is not None and self.min_child_age > self.max_child_age:
            raise ValueError('Minimum child age cannot exceed maximum child age')
        if self.max_total_guests is not None and self.max_total_guests > self.max_adults + self.max_children:
            raise ValueError('Total guests cannot exceed adult and child limits combined')
        return self


class AccommodationDetails(BaseModel):
    model_config = ConfigDict(extra='forbid')
    room_types: list[RoomType] = Field(min_length=1, max_length=25)
    amenities: list[str] = Field(default_factory=list, max_length=30)
    house_rules: str = Field(default='', max_length=600)


class MenuItem(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=2, max_length=100)
    indicative_price_lkr_minor: int | None = Field(default=None, ge=0, le=100_000_000)


class RestaurantDetails(BaseModel):
    model_config = ConfigDict(extra='forbid')
    cuisines: list[str] = Field(min_length=1, max_length=15)
    dietary_options: list[str] = Field(default_factory=list, max_length=15)
    menu_items: list[MenuItem] = Field(default_factory=list, max_length=40)
    opening_notes: str = Field(default='', max_length=500)


class GuideDetails(BaseModel):
    model_config = ConfigDict(extra='forbid')
    languages: list[str] = Field(min_length=1, max_length=15)
    service_areas: list[str] = Field(min_length=1, max_length=30)
    qualification_notes: str = Field(default='', max_length=600)
    indicative_daily_lkr_minor: int | None = Field(default=None, ge=0, le=100_000_000)


class VehicleType(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=2, max_length=100)
    passenger_seats: int = Field(ge=1, le=100)
    luggage_bags: int = Field(ge=0, le=100)
    indicative_day_lkr_minor: int | None = Field(default=None, ge=0, le=100_000_000)


class TransportDetails(BaseModel):
    model_config = ConfigDict(extra='forbid')
    vehicle_types: list[VehicleType] = Field(min_length=1, max_length=30)
    service_areas: list[str] = Field(min_length=1, max_length=30)
    transfer_notes: str = Field(default='', max_length=600)


class ExperienceDetails(BaseModel):
    model_config = ConfigDict(extra='forbid')
    experience_types: list[str] = Field(min_length=1, max_length=30)
    service_areas: list[str] = Field(min_length=1, max_length=30)
    duration_notes: str = Field(default='', max_length=400)
    minimum_age: int | None = Field(default=None, ge=0, le=100)
    indicative_person_lkr_minor: int | None = Field(default=None, ge=0, le=100_000_000)


_DETAIL_TYPES = {
    'accommodation': AccommodationDetails, 'restaurant': RestaurantDetails,
    'guide': GuideDetails, 'transport': TransportDetails,
    'tour_operator': ExperienceDetails, 'activity': ExperienceDetails,
}


def validate_details(category: str, details: dict[str, Any]) -> dict:
    """No unknown/unbounded subtype attributes are stored or later displayed as trusted data."""
    schema = _DETAIL_TYPES.get(category)
    if schema is None:
        raise HTTPException(422, 'Unsupported listing category')
    try:
        validated = schema.model_validate(details).model_dump(mode='json')
    except ValidationError as exc:
        raise HTTPException(422, detail=exc.errors(include_url=False)) from exc
    if len(str(validated)) > 18_000:
        raise HTTPException(422, 'Listing details exceed the permitted size')
    return validated


class ListingWrite(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(min_length=3, max_length=160)
    summary: str = Field(min_length=25, max_length=350)
    description: str = Field(min_length=60, max_length=3500)
    public_email: str | None = Field(default=None, max_length=320)
    public_phone: str | None = Field(default=None, max_length=40)
    details: dict[str, Any]
    latitude: float | None = Field(default=None, ge=-90, le=90, allow_inf_nan=False)
    longitude: float | None = Field(default=None, ge=-180, le=180, allow_inf_nan=False)
    location_source_url: HttpUrl | None = Field(default=None, max_length=2048)
    location_note: str | None = Field(default=None, max_length=250)

    @field_validator('location_source_url')
    @classmethod
    def check_source_host(cls, value: HttpUrl | None):
        if value is None:
            return value
        host = value.host or ''
        if (host.lower() in {'localhost', '127.0.0.1', '::1'} or host.lower().endswith(('.local', '.internal'))
                or value.port not in (None, 443)):
            raise ValueError('Only publicly accessible HTTPS location references are allowed')
        return value

    @model_validator(mode='after')
    def check_location(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError('Supply both latitude and longitude')
        if self.latitude is not None and self.location_source_url is None:
            raise ValueError('A source URL is needed for map coordinates')
        if self.latitude is None and self.location_source_url is not None:
            raise ValueError('Coordinates are required when providing a location source')
        if self.location_source_url is not None and self.location_source_url.scheme != 'https':
            raise ValueError('Location source must be HTTPS')
        return self

    @field_validator('title', 'summary', 'description')
    @classmethod
    def clean_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError('Field must not be blank')
        return cleaned

    @field_validator('public_email')
    @classmethod
    def email_address(cls, value: str | None) -> str | None:
        if not value or not value.strip():
            return None
        value = value.strip().lower()
        if value.count('@') != 1 or '.' not in value.rsplit('@', 1)[-1] or any(c.isspace() for c in value):
            raise ValueError('Supply a valid public contact email')
        return value

    @field_validator('public_phone')
    @classmethod
    def phone_number(cls, value: str | None) -> str | None:
        if not value or not value.strip():
            return None
        value = value.strip()
        if len(value) < 7 or any(c not in '+0123456789 -()' for c in value):
            raise ValueError('Supply a valid public contact number')
        return value


class PhotoWrite(BaseModel):
    model_config = ConfigDict(extra='forbid')
    image_url: str = Field(max_length=2048)
    source_url: str = Field(max_length=2048)
    credit: str = Field(min_length=2, max_length=160)
    license_name: str = Field(min_length=2, max_length=100)
    license_url: str = Field(max_length=2048)
    alt_text: str = Field(min_length=5, max_length=240)

    @field_validator('image_url', 'source_url', 'license_url')
    @classmethod
    def public_https(cls, value: str, info: ValidationInfo) -> str:
        if info.field_name in ('image_url', 'source_url') and re.fullmatch(r'/api/v1/listing-media/[0-9a-fA-F-]{36}', value):
            return value
        if info.field_name == 'license_url' and value == '':
            return value
        try:
            uri = urlsplit(value.strip())
            host = uri.hostname or ''
            safe_port = uri.port in (None, 443)
        except ValueError as exc:
            raise ValueError('Invalid HTTPS reference') from exc
        if (uri.scheme != 'https' or not host or uri.username or uri.password
                or host in {'localhost', '127.0.0.1', '::1'} or host.endswith('.local')
                or host.endswith('.internal') or not safe_port):
            raise ValueError('Only publicly hosted HTTPS references are allowed')
        return value.strip()


class QuickStartListing(BaseModel):
    """Create a genuinely incomplete PRIVATE draft; never auto-publish placeholder data."""
    model_config = ConfigDict(extra='forbid')
    title: str = Field(min_length=3, max_length=160)

    @field_validator('title')
    @classmethod
    def strip_title(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError('Enter a listing title of at least three characters')
        return value


class ListingRevisionWrite(ListingWrite):
    # None means keep currently published gallery; [] explicitly removes all pictures.
    photos: list[PhotoWrite] | None = Field(default=None, max_length=10)


class RevisionDecision(BaseModel):
    model_config = ConfigDict(extra='forbid')
    decision: Literal['approved', 'changes_requested']
    reason: str = Field(min_length=15, max_length=600)

    @field_validator('reason')
    @classmethod
    def clean_reason(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 15:
            raise ValueError('Provide a review explanation of at least 15 characters')
        return value


class ListingDecision(BaseModel):
    model_config = ConfigDict(extra='forbid')
    decision: Literal['published', 'changes_requested']
    reason: str = Field(min_length=15, max_length=600)

    @field_validator('reason')
    @classmethod
    def cleaned_reason(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 15:
            raise ValueError('Provide a review explanation of at least 15 characters')
        return value


def _event(db: Session, actor: User, listing: ServiceListing, action: str, reason: str | None = None) -> None:
    db.add(AuditEvent(actor_id=actor.id, action=action, object_type='service_listing',
                      object_id=listing.id, reason=reason[:300] if reason else None))


def _photo_dict(photo: ServiceListingPhoto) -> dict:
    return {field: getattr(photo, field) for field in
            ('image_url', 'source_url', 'credit', 'license_name', 'license_url', 'alt_text')} | {'id': str(photo.id)}


def listing_dict(item: ServiceListing) -> dict:
    """Carefully curated public response: NO private org contacts, evidence, or internal review rows."""
    return {
        'id': str(item.id), 'slug': item.slug, 'category': item.category,
        'title': item.title, 'summary': item.summary, 'description': item.description,
        'province': item.province, 'district': item.district,
        'public_email': item.public_email, 'public_phone': item.public_phone,
        'details': item.details, 'photos': [_photo_dict(p) for p in item.photos],
        'latitude': item.latitude, 'longitude': item.longitude,
        'location_source_url': item.location_source_url, 'location_note': item.location_note,
        'status': item.status,
        'prices_are_indicative': True, 'booking_available': False,
    }


def _revision_dict(revision: ServiceListingRevision) -> dict:
    return {'id': str(revision.id), 'listing_id': str(revision.listing_id),
            'status': revision.status, 'snapshot': revision.snapshot,
            'review_feedback': revision.review_feedback,
            'created_at': revision.created_at.isoformat() if revision.created_at else None}


def _active_revision(item: ServiceListing) -> ServiceListingRevision | None:
    return next((r for r in reversed(item.revisions)
                 if r.status in ('draft', 'submitted', 'changes_requested')), None)


def _private_dict(item: ServiceListing) -> dict:
    current = _active_revision(item)
    return {**listing_dict(item), 'organization_id': str(item.organization_id),
            'review_feedback': item.review_feedback,
            'revision': _revision_dict(current) if current else None,
            'published_at': item.published_at.isoformat() if item.published_at else None}


def _member_listing(db: Session, org_id: UUID, listing_id: UUID, user: User,
                    roles: tuple[str, ...] = ('owner', 'manager', 'staff')) -> tuple[VendorOrganization, ServiceListing]:
    org = _organization(db, org_id, user, roles)
    item = db.scalar(select(ServiceListing).where(
        ServiceListing.id == listing_id, ServiceListing.organization_id == org.id))
    if item is None:
        raise HTTPException(404, 'Listing not found')
    return org, item


def _draft(item: ServiceListing) -> None:
    if item.status not in ('draft', 'changes_requested'):
        raise HTTPException(409, 'Submitted/published listings cannot be edited; use the review workflow')


def _approved_org(org: VendorOrganization, db: Session) -> None:
    if org.verification_state != 'approved':
        raise HTTPException(409, 'Business verification must be approved first')
    invalid = db.scalar(select(VendorEvidence.id).where(
        VendorEvidence.organization_id == org.id,
        VendorEvidence.expires_on.is_not(None), VendorEvidence.expires_on < date.today()).limit(1))
    if invalid:
        raise HTTPException(409, 'Business has expired evidence and requires re-verification')


def _public_query():
    """Use independent DB-verification checks even if maintenance tasks haven't run."""
    expired = exists(select(VendorEvidence.id).where(
        VendorEvidence.organization_id == VendorOrganization.id,
        VendorEvidence.expires_on.is_not(None), VendorEvidence.expires_on < date.today()))
    return (select(ServiceListing).join(VendorOrganization, ServiceListing.organization_id == VendorOrganization.id)
            .where(ServiceListing.status == 'published', VendorOrganization.verification_state == 'approved', ~expired))


def evaluate_family_fit(details: dict, adults: int, child_ages: list[int]) -> dict:
    """Indicative single-room capacity only; not inventory or confirmed child policy."""
    rooms = []
    for room in details.get('room_types', []):
        age_lower = room.get('min_child_age')
        age_upper = room.get('max_child_age')
        if age_lower is None:
            age_lower = 0
        if age_upper is None:
            age_upper = 17
        guests = adults + len(child_ages)
        fits = (adults <= room['max_adults'] and len(child_ages) <= room['max_children']
                and all(age_lower <= age <= age_upper for age in child_ages)
                and (room.get('max_total_guests') is None or guests <= room['max_total_guests']))
        rooms.append({'room_name': room['name'], 'may_fit': bool(fits),
                      'age_policy_specified': room.get('min_child_age') is not None
                      or room.get('max_child_age') is not None,
                      'max_adults': room['max_adults'], 'max_children': room['max_children']})
    return {'adults': adults, 'child_ages': child_ages, 'rooms': rooms,
            'any_room_may_fit': any(r['may_fit'] for r in rooms),
            'disclaimer': 'Capacity and child-age fit only, based on vendor information. '
                          'No availability, booking, total family price, or final child policy is guaranteed.'}


@public_router.get('/{slug}/family-fit')
def public_family_fit(slug: str,
                      adults: int = Query(ge=1, le=30),
                      child_ages: list[int] = Query(default=[], max_length=30),
                      db: Session = Depends(get_db)):
    if len(child_ages) > 30 or any(age < 0 or age > 17 for age in child_ages):
        raise HTTPException(422, 'Child ages must be between 0 and 17 (up to 30 children)')
    item = db.scalar(_public_query().where(ServiceListing.slug == slug))
    if item is None or item.category != 'accommodation':
        raise HTTPException(404, 'Published accommodation listing not found')
    return evaluate_family_fit(item.details, adults, child_ages)


def _eligible_room_predicate(adults: int, child_ages: list[int]):
    """Filter on PostgreSQL JSONB before pagination, not after a limited result set."""
    room = func.jsonb_array_elements(ServiceListing.details['room_types']).table_valued('value').alias('room')
    value = cast(room.c.value, JSONB)
    checks = [
        cast(value['max_adults'].astext, Integer) >= adults,
        cast(value['max_children'].astext, Integer) >= len(child_ages),
        or_(value['max_total_guests'].astext.is_(None),
            cast(value['max_total_guests'].astext, Integer) >= adults + len(child_ages)),
    ]
    for age in child_ages:
        checks.extend([
            or_(value['min_child_age'].astext.is_(None), cast(value['min_child_age'].astext, Integer) <= age),
            or_(value['max_child_age'].astext.is_(None), cast(value['max_child_age'].astext, Integer) >= age),
        ])
    return exists(select(literal(1)).select_from(room).where(and_(*checks)).correlate(ServiceListing))


def _destination_area_predicate(destination: Destination):
    """Regional discovery, not an assertion the provider is near a POI or entrance."""
    candidates = {destination.district.strip(), destination.slug.replace('-', ' ').strip()}
    candidates.update(t.title.strip() for t in destination.translations if t.locale == 'en')
    areas = func.jsonb_array_elements_text(ServiceListing.details['service_areas']).table_valued('value').alias('area')
    area_match = exists(select(literal(1)).select_from(areas).where(
        func.lower(areas.c.value).in_([v.lower() for v in candidates if v])).correlate(ServiceListing))
    return or_(func.lower(ServiceListing.district) == destination.district.strip().lower(), area_match)


def _distance_meters(latitude: float, longitude: float):
    """PostGIS geography: geodesic distance in metres, never a road/travel distance."""
    point = cast(func.ST_SetSRID(func.ST_MakePoint(ServiceListing.longitude, ServiceListing.latitude), 4326), Geography())
    center = cast(func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326), Geography())
    return func.ST_Distance(point, center)


@public_router.get('')
def public_listings(category: Category | None = None,
                    province: str | None = Query(default=None, max_length=120),
                    district: str | None = Query(default=None, max_length=120),
                    destination: str | None = Query(default=None, max_length=120, pattern=r'^[a-z0-9-]+$'),
                    q: str = Query(default='', max_length=100),
                    adults: int | None = Query(default=None, ge=1, le=30),
                    child_ages: list[int] = Query(default=[]),
                    near_lat: float | None = Query(default=None, ge=-90, le=90, allow_inf_nan=False),
                    near_lon: float | None = Query(default=None, ge=-180, le=180, allow_inf_nan=False),
                    radius_km: float | None = Query(default=None, gt=0, le=100, allow_inf_nan=False),
                    sort: Literal['recent', 'distance'] = 'recent',
                    limit: int = Query(default=24, ge=1, le=60),
                    offset: int = Query(default=0, ge=0, le=1000),
                    db: Session = Depends(get_db)):
    if len(child_ages) > 30 or any(age < 0 or age > 17 for age in child_ages):
        raise HTTPException(422, 'Child ages must be between 0 and 17 (up to 30 children)')
    if (adults is not None or child_ages) and (category != 'accommodation' or adults is None):
        raise HTTPException(422, 'Family matching requires accommodation category and adult count')
    has_center = near_lat is not None and near_lon is not None
    if (near_lat is None) != (near_lon is None):
        raise HTTPException(422, 'Both location coordinates are required')
    if (radius_km is not None or sort == 'distance') and not has_center:
        raise HTTPException(422, 'Provide both coordinates for radius or distance sorting')

    stmt = _public_query()
    if category:
        stmt = stmt.where(ServiceListing.category == category)
    if province and province.strip():
        stmt = stmt.where(ServiceListing.province.ilike(province.strip()))
    if district and district.strip():
        stmt = stmt.where(ServiceListing.district.ilike(district.strip()))
    if q.strip():
        term = f"%{q.strip()}%"
        stmt = stmt.where(or_(ServiceListing.title.ilike(term), ServiceListing.summary.ilike(term),
                              ServiceListing.district.ilike(term)))
    if destination:
        place = db.scalar(select(Destination).where(
            Destination.slug == destination,
            Destination.content_status.in_(['sample', 'published'])))
        if place is None:
            raise HTTPException(404, 'Destination is not available')
        stmt = stmt.where(_destination_area_predicate(place))
    if adults is not None:
        stmt = stmt.where(_eligible_room_predicate(adults, child_ages))

    if has_center:
        distance = _distance_meters(near_lat, near_lon)
        stmt = stmt.where(ServiceListing.latitude.is_not(None), ServiceListing.longitude.is_not(None))
        if radius_km is not None:
            stmt = stmt.where(func.ST_DWithin(
                cast(func.ST_SetSRID(func.ST_MakePoint(ServiceListing.longitude, ServiceListing.latitude), 4326), Geography()),
                cast(func.ST_SetSRID(func.ST_MakePoint(near_lon, near_lat), 4326), Geography()),
                radius_km * 1000))
        order = (distance.asc(), ServiceListing.id.asc()) if sort == 'distance' else (ServiceListing.published_at.desc(), ServiceListing.id.asc())
        results = db.execute(stmt.add_columns(distance.label('distance_m')).order_by(*order).offset(offset).limit(limit)).all()
        return [{**listing_dict(row), 'distance_km': round(float(meters) / 1000, 1)} for row, meters in results]
    rows = db.scalars(stmt.order_by(ServiceListing.published_at.desc(), ServiceListing.id.asc())
                      .offset(offset).limit(limit)).all()
    return [listing_dict(row) for row in rows]


@public_router.get('/{slug}')
def public_listing(slug: str, db: Session = Depends(get_db)):
    row = db.scalar(_public_query().where(ServiceListing.slug == slug))
    if row is None:
        raise HTTPException(404, 'Listing not found')
    return listing_dict(row)


@vendor_router.get('/organizations/{org_id}/listings')
def vendor_listings(org_id: UUID, user: User = Depends(require_user), db: Session = Depends(get_db)):
    org = _organization(db, org_id, user)
    rows = db.scalars(select(ServiceListing).where(ServiceListing.organization_id == org.id)
                      .order_by(ServiceListing.created_at.desc()).limit(100)).all()
    return [_private_dict(row) for row in rows]


def _check_listing_quota(db: Session, org_id: UUID) -> None:
    count = db.scalar(select(func.count()).select_from(ServiceListing).where(
        ServiceListing.organization_id == org_id, ServiceListing.status != 'archived'))
    if count >= 25:
        raise HTTPException(409, 'Maximum 25 active listing records per business')


@vendor_router.post('/organizations/{org_id}/listings/quick-start', status_code=201)
def create_quick_listing(org_id: UUID, body: QuickStartListing,
                         user: User = Depends(require_user), db: Session = Depends(get_db)):
    """Title-only private draft, available before business verification is complete.

    Publication still requires complete server-side fields, approved organization,
    and independent listing moderation. Blank fields are never public.
    """
    org = _organization(db, org_id, user, ('owner', 'manager'))
    _check_listing_quota(db, org.id)
    slug = re.sub(r'[^a-z0-9]+', '-', body.title.lower()).strip('-')[:85].strip('-') or 'listing'
    item = ServiceListing(organization_id=org.id, slug=f'{slug}-{uuid.uuid4().hex[:12]}',
        category=org.category, title=body.title, summary='', description='',
        province=org.province or '', district=org.district or '', details={}, status='draft')
    db.add(item)
    db.flush()
    _event(db, user, item, 'listing.quick_draft.created')
    db.commit()
    return _private_dict(item)


@vendor_router.post('/organizations/{org_id}/listings', status_code=201)
def create_listing(org_id: UUID, body: ListingWrite,
                   user: User = Depends(require_user), db: Session = Depends(get_db)):
    org = _organization(db, org_id, user, ('owner', 'manager'))
    _check_listing_quota(db, org.id)
    details = validate_details(org.category, body.details)
    slug = re.sub(r'[^a-z0-9]+', '-', body.title.lower()).strip('-')[:85].strip('-') or 'listing'
    slug = f'{slug}-{uuid.uuid4().hex[:12]}'
    item = ServiceListing(organization_id=org.id, slug=slug, category=org.category,
        province=org.province or '', district=org.district or '', details=details, **body.model_dump(exclude={'details'}, mode='json'))
    db.add(item)
    db.flush()
    _event(db, user, item, 'listing.created')
    db.commit()
    return _private_dict(item)


@vendor_router.get('/organizations/{org_id}/listings/{listing_id}')
def vendor_listing(org_id: UUID, listing_id: UUID,
                   user: User = Depends(require_user), db: Session = Depends(get_db)):
    _, item = _member_listing(db, org_id, listing_id, user)
    return _private_dict(item)


@vendor_router.put('/organizations/{org_id}/listings/{listing_id}')
def update_listing(org_id: UUID, listing_id: UUID, body: ListingWrite,
                   user: User = Depends(require_user), db: Session = Depends(get_db)):
    _, item = _member_listing(db, org_id, listing_id, user, ('owner', 'manager'))
    _draft(item)
    for key, value in body.model_dump(exclude={'details'}, mode='json').items():
        setattr(item, key, value)
    item.details = validate_details(item.category, body.details)
    _event(db, user, item, 'listing.updated')
    db.commit()
    return _private_dict(item)


@vendor_router.post('/organizations/{org_id}/listings/{listing_id}/photos', status_code=201)
def add_photo(org_id: UUID, listing_id: UUID, body: PhotoWrite,
              user: User = Depends(require_user), db: Session = Depends(get_db)):
    _, item = _member_listing(db, org_id, listing_id, user, ('owner', 'manager'))
    _draft(item)
    if len(item.photos) >= 10:
        raise HTTPException(409, 'Maximum ten photographs per listing')
    photo = ServiceListingPhoto(listing_id=item.id, **body.model_dump())
    db.add(photo)
    _event(db, user, item, 'listing.photo.added')
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, 'This photo source is already attached') from exc
    return _photo_dict(photo)


@vendor_router.delete('/organizations/{org_id}/listings/{listing_id}/photos/{photo_id}')
def remove_photo(org_id: UUID, listing_id: UUID, photo_id: UUID,
                 user: User = Depends(require_user), db: Session = Depends(get_db)):
    _, item = _member_listing(db, org_id, listing_id, user, ('owner', 'manager'))
    _draft(item)
    photo = db.scalar(select(ServiceListingPhoto).where(
        ServiceListingPhoto.id == photo_id, ServiceListingPhoto.listing_id == item.id))
    if photo is None:
        raise HTTPException(404, 'Photo not found')
    db.delete(photo)
    _event(db, user, item, 'listing.photo.removed')
    db.commit()
    return {'removed': True}


@vendor_router.post('/organizations/{org_id}/listings/{listing_id}/submit')
def submit_listing(org_id: UUID, listing_id: UUID,
                   user: User = Depends(require_user), db: Session = Depends(get_db)):
    org, item = _member_listing(db, org_id, listing_id, user, ('owner', 'manager'))
    _draft(item)
    _approved_org(org, db)
    # A quick-start draft is intentionally incomplete. Never submit/publish until
    # EVERY normal ListingWrite constraint is satisfied, including descriptions.
    try:
        ListingWrite.model_validate({
            'title': item.title, 'summary': item.summary, 'description': item.description,
            'public_email': item.public_email, 'public_phone': item.public_phone,
            'details': item.details, 'latitude': item.latitude, 'longitude': item.longitude,
            'location_source_url': item.location_source_url, 'location_note': item.location_note,
        })
    except ValidationError as exc:
        raise HTTPException(422, detail=exc.errors(include_url=False)) from exc
    validate_details(item.category, item.details)
    if not item.public_email and not item.public_phone:
        raise HTTPException(422, 'Supply a public business contact to accept inquiries outside Tourismo')
    item.province = org.province or ''
    item.district = org.district or ''
    item.status = 'submitted'
    item.review_feedback = None
    _event(db, user, item, 'listing.submitted')
    db.commit()
    return _private_dict(item)


@vendor_router.post('/organizations/{org_id}/listings/{listing_id}/archive')
def archive_listing(org_id: UUID, listing_id: UUID,
                    user: User = Depends(require_user), db: Session = Depends(get_db)):
    _, item = _member_listing(db, org_id, listing_id, user, ('owner', 'manager'))
    if item.status == 'archived':
        raise HTTPException(409, 'Listing already archived')
    item.status = 'archived'
    _event(db, user, item, 'listing.archived')
    db.commit()
    return _private_dict(item)


@vendor_router.post('/organizations/{org_id}/listings/{listing_id}/revisions')
def save_revision(org_id: UUID, listing_id: UUID, body: ListingRevisionWrite,
                  user: User = Depends(require_user), db: Session = Depends(get_db)):
    _, item = _member_listing(db, org_id, listing_id, user, ('owner', 'manager'))
    # Lock parent so only one open revision can be created per published listing.
    db.scalar(select(ServiceListing.id).where(ServiceListing.id == item.id).with_for_update())
    if item.status != 'published':
        raise HTTPException(409, 'Revisions are only available for published listings')
    validated = validate_details(item.category, body.details)
    snapshot = body.model_dump(mode='json', exclude={'photos'})
    snapshot['details'] = validated
    if body.photos is None:
        snapshot['photos'] = [{key: getattr(photo,key) for key in
                              ('image_url','source_url','credit','license_name','license_url','alt_text')}
                             for photo in item.photos]
    else:
        photos = [photo.model_dump(mode='json') for photo in body.photos]
        if len({p['source_url'] for p in photos}) != len(photos):
            raise HTTPException(422, 'Photo sources must be unique')
        local_refs = {p['source_url'] for p in photos if p['source_url'].startswith('/api/v1/listing-media/')}
        owned = {p.source_url for p in item.photos}
        if not local_refs.issubset(owned):
            raise HTTPException(422, 'Uploaded photo must belong to this listing')
        snapshot['photos'] = photos
    current = _active_revision(item)
    if current is not None and current.status == 'submitted':
        raise HTTPException(409, 'Revision is awaiting independent review')
    if current is None:
        if len(item.revisions) >= 30:
            raise HTTPException(409, 'Revision history limit reached; contact an administrator')
        current = ServiceListingRevision(id=uuid.uuid4(), listing_id=item.id, author_id=user.id, status='draft', snapshot=snapshot)
        db.add(current)
    else:
        current.snapshot = snapshot
        current.status = 'draft'
        current.review_feedback = None
        current.updated_at = now_utc()
    _event(db, user, item, 'listing.revision.saved')
    db.commit()
    return _revision_dict(current)


@vendor_router.post('/organizations/{org_id}/listings/{listing_id}/revisions/submit')
def submit_revision(org_id: UUID, listing_id: UUID,
                    user: User = Depends(require_user), db: Session = Depends(get_db)):
    org, item = _member_listing(db, org_id, listing_id, user, ('owner', 'manager'))
    db.scalar(select(ServiceListing.id).where(ServiceListing.id == item.id).with_for_update())
    revision = _active_revision(item)
    if item.status != 'published' or revision is None or revision.status not in ('draft', 'changes_requested'):
        raise HTTPException(409, 'No editable published-listing revision is available')
    _approved_org(org, db)
    data = ListingRevisionWrite.model_validate(revision.snapshot)
    validate_details(item.category, data.details)
    if not data.public_email and not data.public_phone:
        raise HTTPException(422, 'A public contact is required')
    revision.status = 'submitted'
    revision.review_feedback = None
    _event(db, user, item, 'listing.revision.submitted')
    db.commit()
    return _revision_dict(revision)


@admin_router.get('/revisions')
def pending_revisions(limit: int = Query(default=50, ge=1, le=100),
                      admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.scalars(select(ServiceListingRevision).where(ServiceListingRevision.status == 'submitted')
                      .order_by(ServiceListingRevision.created_at).limit(limit)).all()
    result=[]
    for rev in rows:
        result.append({**_revision_dict(rev), 'live_title': rev.listing.title,
                       'organization_id': str(rev.listing.organization_id)})
    return result


@admin_router.post('/revisions/{revision_id}/decision')
def decide_revision(revision_id: UUID, body: RevisionDecision,
                    admin: User = Depends(require_admin), db: Session = Depends(get_db),
                    _mfa=Depends(require_privileged_mfa)):
    revision = db.scalar(select(ServiceListingRevision).where(
        ServiceListingRevision.id == revision_id).with_for_update())
    if revision is None:
        raise HTTPException(404, 'Revision not found')
    if revision.status != 'submitted':
        raise HTTPException(409, 'Only submitted revisions can be reviewed')
    item = db.scalar(select(ServiceListing).where(ServiceListing.id == revision.listing_id).with_for_update())
    if item is None or item.status != 'published':
        raise HTTPException(409, 'Listing is no longer published')
    org = db.get(VendorOrganization, item.organization_id)
    if org is None:
        raise HTTPException(409, 'Business no longer exists')
    if org.owner_id == admin.id or db.scalar(select(VendorMembership.id).where(
            VendorMembership.organization_id == org.id, VendorMembership.user_id == admin.id)):
        raise HTTPException(403, 'Cannot review a listing from your own organization')
    if body.decision == 'approved':
        _approved_org(org, db)
        data = ListingRevisionWrite.model_validate(revision.snapshot)
        validate_details(item.category, data.details)
        if not data.public_email and not data.public_phone:
            raise HTTPException(422, 'A public contact is required')
        for key, value in data.model_dump(exclude={'photos'}, mode='json').items():
            setattr(item, key, value)
        if data.photos is not None:
            requested = {photo.source_url: photo for photo in data.photos}
            original = {photo.source_url: photo for photo in item.photos}
            for source, existing in list(original.items()):
                if source not in requested:
                    item.photos.remove(existing)
            db.flush()
            for source, new_photo in requested.items():
                if source in original:
                    existing = original[source]
                    for field, value in new_photo.model_dump(mode='json').items():
                        setattr(existing, field, value)
                else:
                    item.photos.append(ServiceListingPhoto(listing_id=item.id, **new_photo.model_dump(mode='json')))
        item.updated_at = now_utc()
    else:
        revision.review_feedback = body.reason
    revision.status = body.decision
    revision.reviewer_id = admin.id
    revision.reviewed_at = now_utc()
    _event(db, admin, item, 'listing.revision.review.' + body.decision, body.reason)
    db.commit()
    return _revision_dict(revision)


@admin_router.get('')
def admin_review_queue(status: Literal['submitted', 'published', 'changes_requested'] = 'submitted',
                       limit: int = Query(default=50, ge=1, le=100),
                       admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.scalars(select(ServiceListing).where(ServiceListing.status == status)
                      .order_by(ServiceListing.created_at).limit(limit)).all()
    return [_private_dict(row) for row in rows]


@admin_router.get('/{listing_id}')
def admin_listing(listing_id: UUID, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    item = db.get(ServiceListing, listing_id)
    if item is None:
        raise HTTPException(404, 'Listing not found')
    org = db.get(VendorOrganization, item.organization_id)
    return {'listing': _private_dict(item),
            'business_name': org.business_name if org else 'Unavailable',
            'business_verification': org.verification_state if org else 'unknown'}


@admin_router.post('/{listing_id}/decision')
def admin_decide_listing(listing_id: UUID, body: ListingDecision,
                         admin: User = Depends(require_admin), db: Session = Depends(get_db),
                         _mfa=Depends(require_privileged_mfa)):
    item = db.scalar(select(ServiceListing).where(ServiceListing.id == listing_id).with_for_update())
    if item is None:
        raise HTTPException(404, 'Listing not found')
    if item.status != 'submitted':
        raise HTTPException(409, 'Only submitted listings can be reviewed')
    org = db.get(VendorOrganization, item.organization_id)
    if org is None:
        raise HTTPException(409, 'Business no longer exists')
    membership = db.scalar(select(VendorMembership.id).where(
        VendorMembership.organization_id == org.id, VendorMembership.user_id == admin.id))
    if org.owner_id == admin.id or membership:
        raise HTTPException(403, 'Cannot review your own business listing')
    if body.decision == 'published':
        _approved_org(org, db)
        validate_details(item.category, item.details)
        if not item.public_email and not item.public_phone:
            raise HTTPException(422, 'A public contact is required for publication')
    item.status = body.decision
    item.review_feedback = None if body.decision == 'published' else body.reason
    if body.decision == 'published':
        item.published_at = now_utc()
    db.add(ServiceListingReview(listing_id=item.id, reviewer_id=admin.id,
                                decision=body.decision, reason=body.reason))
    _event(db, admin, item, 'listing.review.' + body.decision, body.reason)
    db.commit()
    return _private_dict(item)
