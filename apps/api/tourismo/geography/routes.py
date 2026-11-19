from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, or_
from sqlalchemy.orm import Session
from pydantic import BaseModel
from tourismo.core.database import get_db
from tourismo.core.models import Destination, DestinationTranslation

router = APIRouter(prefix='/api/v1/destinations', tags=['destinations'])


class PhotoResponse(BaseModel):
    image_url: str
    file_page_url: str
    photographer: str
    license_name: str
    license_url: str
    alt_text: str


class DestinationResponse(BaseModel):
    slug: str
    title: str
    district: str
    province: str
    summary: str
    content_status: str
    is_sample: bool
    photo: PhotoResponse | None = None


def shape(row: Destination, locale: str = 'en') -> DestinationResponse:
    translation = next((t for t in row.translations if t.locale == locale), None)
    if translation is None:
        translation = next((t for t in row.translations if t.locale == 'en'), None)
    images = getattr(row, 'photos', [])
    main_photo = next((item for item in images if item.is_primary), None)
    photo = PhotoResponse(image_url=main_photo.image_url, file_page_url=main_photo.file_page_url,
                          photographer=main_photo.photographer, license_name=main_photo.license_name,
                          license_url=main_photo.license_url, alt_text=main_photo.alt_text) if main_photo else None
    return DestinationResponse(photo=photo, slug=row.slug, title=translation.title if translation else row.slug,
                               district=row.district, province=row.province,
                               summary=translation.summary if translation else '',
                               content_status=row.content_status, is_sample=row.content_status == 'sample')


@router.get('', response_model=list[DestinationResponse])
def destinations(q: str = Query(default='', max_length=100), locale: str = Query(default='en', pattern='^(en|si|ta)$'),
                 db: Session = Depends(get_db)):
    stmt = select(Destination).where(Destination.content_status.in_(['published', 'sample']))
    if q.strip():
        term = f"%{q.strip().lower()}%"
        stmt = stmt.join(DestinationTranslation).where(
            or_(DestinationTranslation.title.ilike(term), Destination.slug.ilike(term), Destination.district.ilike(term)))
    return [shape(item, locale) for item in db.scalars(stmt.distinct().order_by(Destination.slug).limit(250)).all()]


@router.get('/{slug}', response_model=DestinationResponse)
def destination(slug: str, locale: str = Query(default='en', pattern='^(en|si|ta)$'), db: Session = Depends(get_db)):
    row = db.scalar(select(Destination).where(Destination.slug == slug, Destination.content_status.in_(['published', 'sample'])))
    if row is None:
        raise HTTPException(status_code=404, detail='Destination not found')
    return shape(row, locale)


# Phase 2.1 — Public editorial content. Drafts are never returned to guests.
from datetime import datetime
from tourismo.core.models import ContentSource, DestinationGuide, PointOfInterest

PUBLIC_STATUSES = ('published', 'sample')


class SourceReference(BaseModel):
    name: str
    url: str | None
    license_status: str
    verified_at: datetime | None


class GuideResponse(BaseModel):
    destination_slug: str
    locale: str
    requested_locale: str
    fallback_used: bool
    overview: str
    highlights: list[str]
    local_tips: list[str]
    content_status: str
    verified_at: datetime | None
    source: SourceReference | None


class PoiResponse(BaseModel):
    slug: str
    title: str
    category: str
    description: str
    local_tips: str
    locale: str
    fallback_used: bool
    content_status: str
    verified_at: datetime | None
    source: SourceReference | None
    latitude: float | None = None
    longitude: float | None = None


def _source_reference(source: ContentSource | None) -> SourceReference | None:
    if source is None:
        return None
    return SourceReference(name=source.name, url=source.url,
                           license_status=source.license_status, verified_at=source.verified_at)


def _public_destination(slug: str, db: Session) -> Destination:
    row = db.scalar(select(Destination).where(
        Destination.slug == slug, Destination.content_status.in_(PUBLIC_STATUSES)))
    if row is None:
        raise HTTPException(status_code=404, detail='Destination not found')
    return row


def _choose_translation(translations, requested_locale: str):
    return next((item for item in translations if item.locale == requested_locale), None) or next(
        (item for item in translations if item.locale == 'en'), None)


@router.get('/{slug}/guide', response_model=GuideResponse)
def destination_guide(slug: str, locale: str = Query(default='en', pattern='^(en|si|ta)$'),
                      db: Session = Depends(get_db)):
    destination_row = _public_destination(slug, db)
    guides = db.scalars(select(DestinationGuide).where(
        DestinationGuide.destination_id == destination_row.id,
        DestinationGuide.content_status.in_(PUBLIC_STATUSES),
        DestinationGuide.locale.in_([locale, 'en']))).all()
    guide = _choose_translation(guides, locale)
    if guide is None:
        raise HTTPException(status_code=404, detail='Destination guide not yet available')
    return GuideResponse(destination_slug=slug, locale=guide.locale, requested_locale=locale,
                         fallback_used=locale != guide.locale, overview=guide.overview,
                         highlights=guide.highlights, local_tips=guide.local_tips,
                         content_status=guide.content_status, verified_at=guide.verified_at,
                         source=_source_reference(guide.source))


@router.get('/{slug}/pois', response_model=list[PoiResponse])
def destination_pois(slug: str, locale: str = Query(default='en', pattern='^(en|si|ta)$'),
                     category: str | None = Query(default=None, min_length=2, max_length=40, pattern=r'^[a-z_]+$'),
                     db: Session = Depends(get_db)):
    destination_row = _public_destination(slug, db)
    stmt = select(PointOfInterest).where(PointOfInterest.destination_id == destination_row.id,
                                         PointOfInterest.content_status.in_(PUBLIC_STATUSES))
    if category:
        stmt = stmt.where(PointOfInterest.category == category)
    results = []
    for poi in db.scalars(stmt.order_by(PointOfInterest.slug).limit(50)).all():
        translation = _choose_translation(poi.translations, locale)
        if translation is None:
            continue
        results.append(PoiResponse(slug=poi.slug, title=translation.title, category=poi.category,
                                   description=translation.description, local_tips=translation.local_tips,
                                   locale=translation.locale, fallback_used=locale != translation.locale,
                                   content_status=poi.content_status, verified_at=poi.verified_at,
                                   source=_source_reference(poi.source),
                                   latitude=getattr(poi, "latitude", None), longitude=getattr(poi, "longitude", None)))
    return results


@router.get('/{slug}/photos', response_model=list[PhotoResponse])
def destination_photos(slug: str, db: Session = Depends(get_db)):
    """Location-specific, credited photo gallery. Never exposes unpublished destinations."""
    place = _public_destination(slug, db)
    return [PhotoResponse(image_url=photo.image_url, file_page_url=photo.file_page_url,
                          photographer=photo.photographer, license_name=photo.license_name,
                          license_url=photo.license_url, alt_text=photo.alt_text)
            for photo in sorted(place.photos, key=lambda item: (not item.is_primary, item.file_page_url))]
