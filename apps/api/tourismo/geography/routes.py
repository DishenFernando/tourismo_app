from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, or_
from sqlalchemy.orm import Session
from pydantic import BaseModel
from tourismo.core.database import get_db
from tourismo.core.models import Destination, DestinationTranslation

router = APIRouter(prefix='/api/v1/destinations', tags=['destinations'])


class DestinationResponse(BaseModel):
    slug: str
    title: str
    district: str
    province: str
    summary: str
    content_status: str
    is_sample: bool


def shape(row: Destination, locale: str = 'en') -> DestinationResponse:
    translation = next((t for t in row.translations if t.locale == locale), None)
    if translation is None:
        translation = next((t for t in row.translations if t.locale == 'en'), None)
    return DestinationResponse(slug=row.slug, title=translation.title if translation else row.slug,
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
    return [shape(item, locale) for item in db.scalars(stmt.distinct().order_by(Destination.slug).limit(30)).all()]


@router.get('/{slug}', response_model=DestinationResponse)
def destination(slug: str, locale: str = Query(default='en', pattern='^(en|si|ta)$'), db: Session = Depends(get_db)):
    row = db.scalar(select(Destination).where(Destination.slug == slug, Destination.content_status.in_(['published', 'sample'])))
    if row is None:
        raise HTTPException(status_code=404, detail='Destination not found')
    return shape(row, locale)
