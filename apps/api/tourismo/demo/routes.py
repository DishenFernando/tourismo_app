"""Explicit, opt-in development preview of UNVERIFIED fictional listings.

The public /api/v1/listings verification gates remain untouched. A deployment with
APP_ENVIRONMENT != development will always return 404, regardless of env flags.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from tourismo.core.config import get_settings
from tourismo.core.database import get_db
from tourismo.core.models import Destination, ServiceListing, VendorOrganization
from tourismo.listings.routes import listing_dict, _destination_area_predicate, _eligible_room_predicate

router = APIRouter(prefix='/api/v1/demo', tags=['development-demo'])


def demo_enabled() -> bool:
    settings = get_settings()
    return (settings.app_environment.strip().lower() == 'development'
            and settings.enable_demo_catalog)


def require_demo() -> None:
    if not demo_enabled():
        raise HTTPException(status_code=404, detail='Demo catalog is unavailable')


def _demo_query():
    return (select(ServiceListing)
            .join(VendorOrganization, ServiceListing.organization_id == VendorOrganization.id)
            .where(ServiceListing.slug.like('tourismo-demo-%'),
                   VendorOrganization.business_name.like('[DEMO] %'),
                   ServiceListing.status == 'draft',
                   VendorOrganization.verification_state == 'draft'))


def demo_dict(item: ServiceListing) -> dict:
    result = listing_dict(item)
    # Synthetic contacts are never displayed as functioning provider contacts.
    result['public_email'] = None
    result['public_phone'] = None
    result['is_demo'] = True
    result['demo_disclaimer'] = (
        'Fictional development-only example. Business is not verified, '
        'listing is not published, and prices are illustrative. '
        'No real provider, contact, booking, or availability exists.'
    )
    return result


@router.get('/status')
def demo_status():
    return {'enabled': demo_enabled()}


@router.get('/listings', dependencies=[Depends(require_demo)])
def demo_listings(category: str | None = Query(default=None, max_length=32),
                  district: str | None = Query(default=None, max_length=120),
                  province: str | None = Query(default=None, max_length=120),
                  destination: str | None = Query(default=None, max_length=120, pattern=r'^[a-z0-9-]+$'),
                  q: str = Query(default='', max_length=100),
                  adults: int | None = Query(default=None, ge=1, le=30),
                  child_ages: list[int] = Query(default=[]),
                  limit: int = Query(default=60, ge=1, le=60),
                  db: Session = Depends(get_db)):
    stmt = _demo_query()
    if category:
        stmt = stmt.where(ServiceListing.category == category)
    if district:
        stmt = stmt.where(ServiceListing.district.ilike(district.strip()))
    if province:
        stmt = stmt.where(ServiceListing.province.ilike(province.strip()))
    if destination:
        place = db.scalar(select(Destination).where(
            Destination.slug == destination, Destination.content_status.in_(['sample', 'published'])))
        if place is None:
            raise HTTPException(404, 'Destination is not available')
        stmt = stmt.where(_destination_area_predicate(place))
    if len(child_ages) > 30 or any(age < 0 or age > 17 for age in child_ages):
        raise HTTPException(422, 'Child ages must be between 0 and 17 (up to 30 children)')
    if (adults is not None or child_ages) and (category != 'accommodation' or adults is None):
        raise HTTPException(422, 'Family matching requires accommodation category and adult count')
    if adults is not None:
        stmt = stmt.where(_eligible_room_predicate(adults, child_ages))
    if q.strip():
        stmt = stmt.where(ServiceListing.title.ilike(f'%{q.strip()}%'))
    rows = db.scalars(stmt.order_by(ServiceListing.category, ServiceListing.slug).limit(limit)).all()
    return [demo_dict(row) for row in rows]


@router.get('/listings/{slug}', dependencies=[Depends(require_demo)])
def demo_listing(slug: str, db: Session = Depends(get_db)):
    row = db.scalar(_demo_query().where(ServiceListing.slug == slug))
    if row is None:
        raise HTTPException(status_code=404, detail='Demo listing not found')
    return demo_dict(row)
