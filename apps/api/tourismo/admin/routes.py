"""Editorial CMS. Draft writes require editor; publishing requires administrator."""
from typing import Literal
from urllib.parse import urlsplit
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator as pydantic_model_validator
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from tourismo.admin.permissions import require_editor, require_admin
from tourismo.core.database import get_db
from tourismo.core.models import (User, Destination, DestinationTranslation, DestinationGuide,
                                  PointOfInterest, PoiTranslation, DestinationPhoto,
                                  ContentSource, AuditEvent, GuideRevision, now_utc)
from tourismo.geography.routes import shape, DestinationResponse

router = APIRouter(prefix='/api/v1/admin', tags=['editorial-admin'])


class CreatePlace(BaseModel):
    model_config = ConfigDict(extra='forbid')
    slug: str = Field(pattern=r'^[a-z0-9]+(?:-[a-z0-9]+)*$', max_length=120)
    title: str = Field(min_length=2, max_length=160)
    district: str = Field(min_length=2, max_length=120)
    province: str = Field(min_length=2, max_length=120)
    summary: str = Field(default='Editorial review pending', max_length=2500)


class GuideEdit(BaseModel):
    model_config = ConfigDict(extra='forbid')
    locale: Literal['en', 'si', 'ta'] = 'en'
    overview: str = Field(min_length=30, max_length=10000)
    highlights: list[str] = Field(default_factory=list, max_length=12)
    local_tips: list[str] = Field(default_factory=list, max_length=12)
    source_url: str | None = Field(default=None, max_length=2048)
    source_name: str | None = Field(default=None, max_length=160)

    @field_validator('source_url')
    @classmethod
    def safe_source(cls, value):
        if value and (urlsplit(value).scheme != 'https' or not urlsplit(value).hostname):
            raise ValueError('Sources must use HTTPS')
        return value


class PoiCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    slug: str = Field(pattern=r'^[a-z0-9]+(?:-[a-z0-9]+)*$', max_length=120)
    title: str = Field(min_length=2, max_length=160)
    category: Literal['heritage', 'nature', 'landmark', 'beach', 'wildlife', 'culture', 'adventure']
    description: str = Field(min_length=10, max_length=4000)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    source_url: str | None = Field(default=None, max_length=2048)
    source_name: str | None = Field(default=None, max_length=160)

    @field_validator('source_url')
    @classmethod
    def source_https(cls, value):
        if value and (urlsplit(value).scheme != 'https' or not urlsplit(value).hostname):
            raise ValueError('Sources must use HTTPS')
        return value

    @pydantic_model_validator(mode='after')
    def coordinates_together(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError('Provide both latitude and longitude, or neither')
        if self.latitude is not None and not (self.source_url and self.source_name):
            raise ValueError('Coordinates require an identifiable HTTPS source')
        return self


class PhotoCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    filename: str = Field(min_length=5, max_length=200, pattern=r'^[A-Za-z0-9_.,()%+\-]+\.(?:jpg|jpeg|png|JPG|JPEG|PNG)$')
    photographer: str = Field(min_length=2, max_length=160)
    license_name: Literal['CC BY 4.0', 'CC BY-SA 4.0', 'CC BY-SA 3.0']
    alt_text: str = Field(min_length=8, max_length=240)


def _place(db: Session, slug: str) -> Destination:
    place = db.scalar(select(Destination).where(Destination.slug == slug))
    if place is None:
        raise HTTPException(status_code=404, detail='Destination not found')
    return place


def _audit(db, actor, action, obj, reason=None):
    db.add(AuditEvent(actor_id=actor.id, action=action, object_type='destination',
                      object_id=obj.id, reason=reason))


def _latest_revision(db: Session, guide_id):
    return db.scalar(select(GuideRevision).where(GuideRevision.guide_id == guide_id)
                     .order_by(GuideRevision.version.desc()).limit(1))


def _edit_revision(db: Session, guide: DestinationGuide, data: GuideEdit, editor: User):
    previous = _latest_revision(db, guide.id)
    if previous is not None and previous.status == 'submitted':
        raise HTTPException(status_code=409, detail='This guide revision is awaiting administrator review')
    revision = previous if previous is not None and previous.status == 'draft' else GuideRevision(
        guide_id=guide.id, version=(previous.version + 1 if previous else 1), edited_by=editor.id)
    revision.overview = data.overview.strip()
    revision.highlights = data.highlights
    revision.local_tips = data.local_tips
    revision.status = 'draft'
    revision.edited_by = editor.id
    if data.source_url and data.source_name:
        source = ContentSource(name=data.source_name.strip(), url=data.source_url,
                               license_status='reference_link_only')
        db.add(source)
        db.flush()
        revision.source_id = source.id
    else:
        revision.source_id = None  # Never silently reuse an old verified source for changed text.
    db.add(revision)
    return revision


@router.get('/content-audit')
def content_audit(db: Session = Depends(get_db), editor: User = Depends(require_editor)):
    """Editorial coverage, not a claim of factual verification or a public rating."""
    places = db.scalars(select(Destination).order_by(Destination.slug).limit(500)).all()
    guides = db.scalars(select(DestinationGuide)).all()
    pois = db.scalars(select(PointOfInterest)).all()
    guide_map = {}
    for guide in guides:
        guide_map.setdefault(guide.destination_id, []).append(guide)
    poi_map = {}
    for poi in pois:
        poi_map.setdefault(poi.destination_id, []).append(poi)
    records = []
    for place in places:
        guide_rows = guide_map.get(place.id, [])
        published_guides = [g for g in guide_rows if g.content_status == 'published']
        has_english_guide = any(g.locale == 'en' for g in published_guides)
        translated = sorted(g.locale for g in published_guides if g.locale in ('si', 'ta'))
        photos = len(getattr(place, 'photos', []))
        visible_pois = [item for item in poi_map.get(place.id, []) if item.content_status == 'published']
        missing = []
        if place.content_status != 'published':
            missing.append('destination_unreviewed')
        if not has_english_guide:
            missing.append('english_guide_unreviewed')
        if not photos:
            missing.append('licensed_photo_missing')
        if not visible_pois:
            missing.append('approved_attractions_missing')
        if 'si' not in translated:
            missing.append('sinhala_translation_missing')
        if 'ta' not in translated:
            missing.append('tamil_translation_missing')
        records.append({'slug':place.slug, 'title':next((t.title for t in place.translations
                        if t.locale == 'en'),place.slug), 'status':place.content_status,
                        'photo_count':photos, 'approved_poi_count':len(visible_pois),
                        'reviewed_locales':sorted(g.locale for g in published_guides),
                        'missing':missing})
    return {'total':len(records), 'published':sum(row['status']=='published' for row in records),
            'sample':sum(row['status']=='sample' for row in records),
            'needs_attention':sum(bool(row['missing']) for row in records),
            'destinations':records}


@router.get('/destinations', response_model=list[DestinationResponse])
def list_all(status: Literal['draft', 'sample', 'published'] | None = None,
             db: Session = Depends(get_db), editor: User = Depends(require_editor)):
    stmt = select(Destination)
    if status:
        stmt = stmt.where(Destination.content_status == status)
    return [shape(row) for row in db.scalars(stmt.order_by(Destination.slug).limit(500)).all()]


@router.post('/destinations', response_model=DestinationResponse, status_code=201)
def create_place(data: CreatePlace, db: Session = Depends(get_db), editor: User = Depends(require_editor)):
    place = Destination(slug=data.slug, district=data.district, province=data.province, content_status='draft')
    try:
        db.add(place)
        db.flush()
        db.add(DestinationTranslation(destination_id=place.id, locale='en',
                                      title=data.title.strip(), summary=data.summary.strip()))
        _audit(db, editor, 'destination.create_draft', place)
        db.commit()
        db.refresh(place)
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail='Destination slug already exists') from error
    return shape(place)


@router.put('/destinations/{slug}/guide')
def save_guide(slug: str, data: GuideEdit, db: Session = Depends(get_db),
               editor: User = Depends(require_editor)):
    place = _place(db, slug)
    guide = db.scalar(select(DestinationGuide).where(
        DestinationGuide.destination_id == place.id, DestinationGuide.locale == data.locale))
    if guide is None:
        guide = DestinationGuide(destination_id=place.id, locale=data.locale)
        db.add(guide)
    if guide.content_status in ('published', 'sample'):
        # Editing an existing public guide must never hide the approved content.
        revision = _edit_revision(db, guide, data, editor)
        _audit(db, editor, 'destination.guide_revision_draft', place, f'{data.locale}:v{revision.version}')
    else:
        if guide.content_status == 'submitted':
            raise HTTPException(status_code=409, detail='This guide is awaiting administrator review')
        guide.overview = data.overview.strip()
        guide.highlights = data.highlights
        guide.local_tips = data.local_tips
        guide.content_status = 'draft'
        guide.verified_at = None
        if data.source_url and data.source_name:
            source = ContentSource(name=data.source_name.strip(), url=data.source_url,
                                   license_status='reference_link_only')
            db.add(source)
            db.flush()
            guide.source_id = source.id
        else:
            guide.source_id = None
        _audit(db, editor, 'destination.guide_draft', place, data.locale)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail='Concurrent guide revision; reload and try again') from error
    return {'status': 'draft', 'destination_slug':slug, 'locale':data.locale}


@router.post('/destinations/{slug}/pois', status_code=201)
def add_poi(slug: str, data: PoiCreate, db: Session = Depends(get_db),
            editor: User = Depends(require_editor)):
    place = _place(db, slug)
    poi = PointOfInterest(destination_id=place.id, slug=data.slug, category=data.category, content_status='draft',
                          latitude=data.latitude, longitude=data.longitude)
    if data.latitude is not None:
        poi.location = func.ST_SetSRID(func.ST_MakePoint(data.longitude, data.latitude), 4326)
    try:
        db.add(poi)
        db.flush()
        db.add(PoiTranslation(poi_id=poi.id, locale='en', title=data.title.strip(),
                              description=data.description.strip()))
        if data.source_url and data.source_name:
            if urlsplit(data.source_url).scheme != 'https' or not urlsplit(data.source_url).hostname:
                raise HTTPException(status_code=422, detail='Source must use HTTPS')
            source = ContentSource(name=data.source_name.strip(), url=data.source_url, license_status='reference_link_only')
            db.add(source)
            db.flush()
            poi.source_id = source.id
        _audit(db, editor, 'destination.poi_draft', place, data.slug)
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail='Point-of-interest slug already exists') from error
    return {'slug':data.slug, 'content_status':'draft'}


@router.post('/destinations/{slug}/photos', status_code=201)
def add_photo(slug: str, data: PhotoCreate, db: Session = Depends(get_db),
              editor: User = Depends(require_admin)):
    place = _place(db, slug)
    base = 'https://commons.wikimedia.org/wiki/'
    link = base + 'File:' + data.filename
    image_url = base + 'Special:FilePath/' + data.filename + '?width=1280'
    license_path = 'by-sa/3.0/' if data.license_name == 'CC BY-SA 3.0' else (
        'by/4.0/' if data.license_name == 'CC BY 4.0' else 'by-sa/4.0/')
    photo = DestinationPhoto(destination_id=place.id, image_url=image_url,
                             file_page_url=link, photographer=data.photographer,
                             license_name=data.license_name,
                             license_url='https://creativecommons.org/licenses/'+license_path,
                             alt_text=data.alt_text, is_primary=True, media_kind='commons_photo')
    try:
        for existing in place.photos:
            existing.is_primary = False
        db.add(photo)
        _audit(db, editor, 'destination.photo_added', place, data.filename)
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail='Photo is already attached') from error
    return {'image_url':photo.image_url, 'file_page_url':photo.file_page_url}


@router.post('/destinations/{slug}/publish')
def publish(slug: str, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    place = _place(db, slug)
    guide = db.scalar(select(DestinationGuide).where(
        DestinationGuide.destination_id == place.id, DestinationGuide.locale == 'en'))
    has_name = any(t.locale == 'en' and t.title.strip() for t in place.translations)
    if not has_name or guide is None or not guide.source_id or len(guide.overview.strip()) < 30:
        raise HTTPException(status_code=422, detail='An English title and sourced English guide are required before publishing')
    if guide.content_status in ('published', 'sample'):
        revision = _latest_revision(db, guide.id)
        if revision is not None and revision.status in ('draft', 'submitted'):
            raise HTTPException(status_code=409, detail='Review the pending guide revision first')
    from tourismo.core.models import now_utc
    guide.content_status = 'published'
    guide.verified_at = now_utc()
    place.content_status = 'published'
    # POIs remain drafts until separately editorially approved; no automatic publish of user-written content.
    _audit(db, admin, 'destination.publish', place)
    db.commit()
    return {'slug':slug, 'content_status':'published'}


@router.get('/destinations/{slug}/guide')
def read_draft_guide(slug: str, locale: Literal['en', 'si', 'ta'] = 'en',
                     db: Session = Depends(get_db), editor: User = Depends(require_editor)):
    place = _place(db, slug)
    guide = db.scalar(select(DestinationGuide).where(
        DestinationGuide.destination_id == place.id, DestinationGuide.locale == locale))
    if guide is None:
        return {'locale': locale, 'overview': '', 'highlights': [], 'local_tips': [],
                'source_url': '', 'source_name': '', 'content_status': 'missing'}
    revision = _latest_revision(db, guide.id) if guide.content_status in ('published', 'sample') else None
    content = revision if revision is not None and revision.status in ('draft', 'submitted') else guide
    source = content.source
    return {'locale': locale, 'overview':content.overview, 'highlights':content.highlights,
            'local_tips':content.local_tips, 'source_url':source.url if source else '',
            'source_name':source.name if source else '',
            'content_status': content.status if isinstance(content, GuideRevision) else guide.content_status,
            'live_content_status':guide.content_status,
            'version':revision.version if isinstance(content, GuideRevision) else None}


@router.get('/destinations/{slug}/pois')
def admin_pois(slug: str, db: Session = Depends(get_db), editor: User = Depends(require_editor)):
    place = _place(db, slug)
    results = db.scalars(select(PointOfInterest).where(PointOfInterest.destination_id == place.id)
                         .order_by(PointOfInterest.slug)).all()
    return [{'slug':p.slug, 'title':next((t.title for t in p.translations if t.locale == 'en'),p.slug),
             'content_status':p.content_status, 'has_source':bool(p.source_id),
             'latitude':p.latitude, 'longitude':p.longitude} for p in results]


@router.post('/destinations/{slug}/pois/{poi_slug}/publish')
def approve_poi(slug: str, poi_slug: str, db: Session = Depends(get_db),
                admin: User = Depends(require_admin)):
    place = _place(db,slug)
    poi = db.scalar(select(PointOfInterest).where(PointOfInterest.destination_id == place.id,
                                                  PointOfInterest.slug == poi_slug))
    if poi is None:
        raise HTTPException(status_code=404, detail='Attraction not found')
    if place.content_status != 'published' or not poi.source_id or not poi.translations:
        raise HTTPException(status_code=422, detail='Publish the destination and add sourced attraction details first')
    poi.content_status = 'published'
    from tourismo.core.models import now_utc
    poi.verified_at = now_utc()
    _audit(db,admin,'destination.poi_publish',place,poi_slug)
    db.commit()
    return {'slug':poi_slug,'content_status':'published'}


class ReviewDecision(BaseModel):
    model_config = ConfigDict(extra='forbid')
    reason: str = Field(min_length=8, max_length=300)


@router.get('/review-queue')
def review_queue(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Only submitted content. Never exposes it through public destination APIs."""
    guides = db.scalars(select(DestinationGuide).where(
        DestinationGuide.content_status == 'submitted').order_by(DestinationGuide.updated_at)).all()
    pending = db.scalars(select(GuideRevision).where(GuideRevision.status == 'submitted')).all()
    pending_guides = db.scalars(select(DestinationGuide).where(
        DestinationGuide.id.in_([item.guide_id for item in pending]))).all() if pending else []
    pending_guide_by_id = {item.id: item for item in pending_guides}
    pois = db.scalars(select(PointOfInterest).where(
        PointOfInterest.content_status == 'submitted').order_by(PointOfInterest.created_at)).all()
    destination_ids = ({item.destination_id for item in (*guides, *pois)} |
                       {item.destination_id for item in pending_guides})
    places = db.scalars(select(Destination).where(Destination.id.in_(destination_ids))).all() if destination_ids else []
    slugs = {item.id: item.slug for item in places}
    revisions = [{'kind':'guide', 'destination_slug':slugs.get(pending_guide_by_id[r.guide_id].destination_id),
                  'locale':pending_guide_by_id[r.guide_id].locale, 'status':'submitted',
                  'has_source':bool(r.source_id), 'version':r.version}
                 for r in pending if r.guide_id in pending_guide_by_id]
    return ([{'kind': 'guide', 'destination_slug': slugs.get(g.destination_id),
              'locale': g.locale, 'status':g.content_status, 'has_source': bool(g.source_id)} for g in guides]
            + revisions + [{'kind':'poi', 'destination_slug':slugs.get(p.destination_id), 'poi_slug':p.slug,
                'status':p.content_status, 'has_source':bool(p.source_id)} for p in pois])


@router.post('/destinations/{slug}/guide/submit')
def submit_guide(slug: str, locale: Literal['en', 'si', 'ta'] = 'en',
                 db: Session = Depends(get_db), editor: User = Depends(require_editor)):
    place = _place(db, slug)
    guide = db.scalar(select(DestinationGuide).where(
        DestinationGuide.destination_id == place.id, DestinationGuide.locale == locale))
    if guide is None:
        raise HTTPException(status_code=422, detail='Save a sourced guide draft before requesting review')
    if guide.content_status in ('published', 'sample'):
        revision = _latest_revision(db, guide.id)
        if revision is None or revision.status != 'draft' or not revision.source_id or len(revision.overview.strip()) < 30:
            raise HTTPException(status_code=422, detail='Save a sourced revision draft before requesting review')
        revision.status = 'submitted'
    else:
        if guide.content_status != 'draft' or not guide.source_id or len(guide.overview.strip()) < 30:
            raise HTTPException(status_code=422, detail='Save a sourced guide draft before requesting review')
        guide.content_status = 'submitted'
    _audit(db, editor, 'destination.guide_submitted', place, locale)
    db.commit()
    return {'locale':locale, 'content_status':'submitted'}


@router.post('/destinations/{slug}/pois/{poi_slug}/submit')
def submit_poi(slug: str, poi_slug: str, db: Session = Depends(get_db),
               editor: User = Depends(require_editor)):
    place = _place(db, slug)
    poi = db.scalar(select(PointOfInterest).where(PointOfInterest.destination_id == place.id,
                                                   PointOfInterest.slug == poi_slug))
    if poi is None:
        raise HTTPException(status_code=404, detail='Attraction not found')
    if poi.content_status != 'draft' or not poi.source_id or not poi.translations:
        raise HTTPException(status_code=422, detail='Save sourced attraction details before requesting review')
    poi.content_status = 'submitted'
    _audit(db, editor, 'destination.poi_submitted', place, poi_slug)
    db.commit()
    return {'slug':poi_slug, 'content_status':'submitted'}


@router.post('/destinations/{slug}/guide/request-changes')
def reject_guide(slug: str, decision: ReviewDecision, locale: Literal['en', 'si', 'ta'] = 'en',
                 db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    place = _place(db, slug)
    guide = db.scalar(select(DestinationGuide).where(
        DestinationGuide.destination_id == place.id, DestinationGuide.locale == locale))
    if guide is None:
        raise HTTPException(status_code=409, detail='Only submitted guides can be returned for changes')
    if guide.content_status in ('published', 'sample'):
        revision = _latest_revision(db, guide.id)
        if revision is None or revision.status != 'submitted':
            raise HTTPException(status_code=409, detail='Only submitted revisions can be returned for changes')
        revision.status = 'draft'
    else:
        if guide.content_status != 'submitted':
            raise HTTPException(status_code=409, detail='Only submitted guides can be returned for changes')
        guide.content_status = 'draft'
    _audit(db, admin, 'destination.guide_changes_requested', place, f'{locale}: {decision.reason}'[:300])
    db.commit()
    return {'locale':locale, 'content_status':'draft'}


@router.post('/destinations/{slug}/pois/{poi_slug}/request-changes')
def reject_poi(slug: str, poi_slug: str, decision: ReviewDecision,
                db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    place = _place(db, slug)
    poi = db.scalar(select(PointOfInterest).where(PointOfInterest.destination_id == place.id,
                                                   PointOfInterest.slug == poi_slug))
    if poi is None:
        raise HTTPException(status_code=404, detail='Attraction not found')
    if poi.content_status != 'submitted':
        raise HTTPException(status_code=409, detail='Only submitted attractions can be returned for changes')
    poi.content_status = 'draft'
    _audit(db, admin, 'destination.poi_changes_requested', place, decision.reason)
    db.commit()
    return {'slug':poi_slug, 'content_status':'draft'}


@router.post('/destinations/{slug}/guide/approve')
def approve_guide(slug: str, locale: Literal['en', 'si', 'ta'] = 'en',
                  db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Explicit review approval. Translating a guide does not alter English content."""
    place = _place(db, slug)
    guide = db.scalar(select(DestinationGuide).where(
        DestinationGuide.destination_id == place.id, DestinationGuide.locale == locale))
    if guide is None:
        raise HTTPException(status_code=409, detail='Only submitted and sourced guides can be approved')
    revision = _latest_revision(db, guide.id) if guide.content_status in ('published', 'sample') else None
    content = revision if revision is not None and revision.status == 'submitted' else guide
    if ((isinstance(content, GuideRevision) and not content.source_id) or
            (content is guide and (guide.content_status != 'submitted' or not guide.source_id))):
        raise HTTPException(status_code=409, detail='Only submitted and sourced guides can be approved')
    if len(content.overview.strip()) < 30:
        raise HTTPException(status_code=422, detail='Guide overview must be at least 30 characters')
    if locale != 'en' and place.content_status != 'published':
        raise HTTPException(status_code=422, detail='Publish the English destination guide before translations')
    if locale == 'en':
        has_name = any(t.locale == 'en' and t.title.strip() for t in place.translations)
        if not has_name:
            raise HTTPException(status_code=422, detail='An English destination title is required')
        place.content_status = 'published'
    if isinstance(content, GuideRevision):
        guide.overview = content.overview
        guide.highlights = content.highlights
        guide.local_tips = content.local_tips
        guide.source_id = content.source_id
        content.status = 'approved'
        content.reviewed_by = admin.id
        content.reviewed_at = now_utc()
    guide.content_status = 'published'
    guide.verified_at = now_utc()
    _audit(db, admin, 'destination.guide_approved', place,
           f'{locale}:v{content.version}' if isinstance(content, GuideRevision) else locale)
    db.commit()
    return {'slug':slug, 'locale':locale, 'content_status':'published'}
