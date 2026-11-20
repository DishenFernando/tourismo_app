"""Development-only vendor photo uploads with strict public publication gating.

No image-generation API or production object store is enabled. Every file is
sanitized and must depict the vendor's real service with rights confirmed.
"""
import hashlib
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from tourismo.admin.media import MAX_UPLOAD_BYTES, sanitize_image
from tourismo.core.config import get_settings
from tourismo.core.database import get_db
from tourismo.core.models import (ServiceListing, ServiceListingPhoto, ServiceListingImageBlob, User)
from tourismo.identity.security import require_user
from tourismo.listings.routes import _member_listing, _draft, _event, _public_query

vendor_router = APIRouter(prefix='/api/v1/vendor', tags=['vendor-listing-media'])
public_router = APIRouter(prefix='/api/v1/listing-media', tags=['public-listing-media'])


def require_development_media() -> None:
    if get_settings().app_environment != 'development':
        raise HTTPException(503, 'Production listing uploads require managed media storage')


@vendor_router.post('/organizations/{org_id}/listings/{listing_id}/photos/upload', status_code=201)
async def upload_listing_photo(org_id: UUID, listing_id: UUID, file: UploadFile = File(...),
                               creator: str = Form(...), alt_text: str = Form(...),
                               rights_confirmed: bool = Form(...),
                               user: User = Depends(require_user), db: Session = Depends(get_db)):
    require_development_media()
    _, item = _member_listing(db, org_id, listing_id, user, ('owner', 'manager'))
    _draft(item)
    if not rights_confirmed:
        raise HTTPException(422, 'Confirm permission to use this real service photograph')
    creator, alt_text = creator.strip(), alt_text.strip()
    if not 2 <= len(creator) <= 160 or not 8 <= len(alt_text) <= 240:
        raise HTTPException(422, 'Photographer and accessible description are required')
    if len(item.photos) >= 10:
        raise HTTPException(409, 'Maximum ten photographs per listing')
    if file.content_type not in ('image/jpeg', 'image/png'):
        raise HTTPException(415, 'Only JPEG/PNG photographs are accepted')
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    await file.close()
    try:
        cleaned = sanitize_image(content)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    photo_id = uuid4()
    url = f'/api/v1/listing-media/{photo_id}'
    photo = ServiceListingPhoto(id=photo_id, listing_id=item.id,
        image_url=url, source_url=url, credit=creator, license_name='Creator-authorized photograph',
        license_url='', alt_text=alt_text)
    db.add(photo)
    db.add(ServiceListingImageBlob(photo_id=photo_id, content_type='image/jpeg', data=cleaned,
                                   sha256=hashlib.sha256(cleaned).hexdigest()))
    _event(db, user, item, 'listing.media_uploaded', 'Creator-authorized upload')
    db.commit()
    return dict(id=str(photo_id), image_url=url, source_url=url,
                credit=creator, license_name=photo.license_name, license_url='', alt_text=alt_text)


@vendor_router.get('/organizations/{org_id}/listings/{listing_id}/photos/{photo_id}/preview')
def preview_listing_photo(org_id: UUID, listing_id: UUID, photo_id: UUID,
                          user: User = Depends(require_user), db: Session = Depends(get_db)):
    _member_listing(db, org_id, listing_id, user)
    record = db.execute(select(ServiceListingImageBlob, ServiceListingPhoto)
        .join(ServiceListingPhoto, ServiceListingPhoto.id == ServiceListingImageBlob.photo_id)
        .where(ServiceListingImageBlob.photo_id == photo_id,
               ServiceListingPhoto.listing_id == listing_id)).first()
    if not record:
        raise HTTPException(404, 'Photograph not found')
    blob, _ = record
    if hashlib.sha256(blob.data).hexdigest() != blob.sha256:
        raise HTTPException(409, 'Photograph integrity check failed')
    return Response(content=blob.data, media_type='image/jpeg', headers={
        'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff'})


@public_router.get('/{photo_id}')
def read_listing_photo(photo_id: UUID, db: Session = Depends(get_db)):
    record = db.execute(select(ServiceListingImageBlob, ServiceListingPhoto)
        .join(ServiceListingPhoto, ServiceListingPhoto.id == ServiceListingImageBlob.photo_id)
        .where(ServiceListingImageBlob.photo_id == photo_id)).first()
    if record is None:
        raise HTTPException(404, 'Photograph not found')
    blob, photo = record
    # Reuse exactly the same public-business/verification/expiry gate as listing discovery.
    published = db.scalar(_public_query().where(ServiceListing.id == photo.listing_id))
    if published is None:
        raise HTTPException(404, 'Photograph not public')
    if hashlib.sha256(blob.data).hexdigest() != blob.sha256:
        raise HTTPException(409, 'Photo integrity check failed')
    return Response(content=blob.data, media_type='image/jpeg', headers={
        'Cache-Control': 'public, max-age=300', 'X-Content-Type-Options': 'nosniff'})
