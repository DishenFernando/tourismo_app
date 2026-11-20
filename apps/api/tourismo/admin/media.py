"""Development-only destination image uploads with explicit media provenance.

No third-party generator calls and no image inspection claiming to verify location.
Small sanitized JPEGs are persisted in PostgreSQL for local demos. In production,
use a private signed object-storage upload pipeline and moderation before release.
"""
import hashlib
import io
import uuid
import warnings
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session

from tourismo.admin.permissions import require_admin
from tourismo.core.config import get_settings
from tourismo.core.database import get_db
from tourismo.core.models import AuditEvent, Destination, DestinationPhoto, DestinationImageBlob, User

MAX_UPLOAD_BYTES = 3 * 1024 * 1024
MAX_PIXELS = 12_000_000
MEDIA_PREFIX = '/api/v1/destination-media/'

admin_router = APIRouter(prefix='/api/v1/admin', tags=['editorial-admin'])
public_router = APIRouter(prefix='/api/v1/destination-media', tags=['destination-media'])


def sanitize_image(content: bytes) -> bytes:
    """Decode actual bytes, strip metadata, cap dimensions, re-encode as JPEG."""
    if not content or len(content) > MAX_UPLOAD_BYTES:
        raise ValueError('Image must be smaller than 3 MB')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as raw:
                if raw.format not in {'JPEG', 'PNG'}:
                    raise ValueError('Only JPEG and PNG photographs/illustrations are accepted')
                if raw.width * raw.height > MAX_PIXELS:
                    raise ValueError('Image resolution exceeds the 12 megapixel limit')
                image = ImageOps.exif_transpose(raw).convert('RGB')
                image.thumbnail((1920, 1920), Image.Resampling.LANCZOS)
                result = io.BytesIO()
                image.save(result, format='JPEG', quality=84, optimize=True)
                return result.getvalue()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError('Invalid or unsafe image file') from exc


@admin_router.post('/destinations/{slug}/photos/upload', status_code=201)
async def upload_photo(slug: str,
                       file: UploadFile = File(...),
                       kind: Literal['owned_photo', 'ai_illustration'] = Form(...),
                       creator: str = Form(...),
                       alt_text: str = Form(...),
                       rights_confirmed: bool = Form(...),
                       db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    if get_settings().app_environment != 'development':
        raise HTTPException(503, 'Local media uploads are disabled outside development; configure private cloud media storage')
    if not rights_confirmed:
        raise HTTPException(422, 'Confirm you own or have permission to use this image')
    creator = creator.strip()
    alt_text = alt_text.strip()
    if not 2 <= len(creator) <= 160 or not 8 <= len(alt_text) <= 240:
        raise HTTPException(422, 'Creator/tool and accessible description are required')
    if file.content_type not in ('image/jpeg', 'image/png'):
        raise HTTPException(415, 'Upload a JPEG or PNG file')
    destination = db.scalar(select(Destination).where(Destination.slug == slug))
    if destination is None:
        raise HTTPException(404, 'Destination not found')
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    await file.close()
    try:
        cleaned = sanitize_image(content)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    photo_id = uuid.uuid4()
    url = MEDIA_PREFIX + str(photo_id)
    # Never classify an AI image as factual photography. Prefer existing
    # photographs as a destination's cover when there is already a cover.
    primary = not any(p.is_primary for p in destination.photos)
    photo = DestinationPhoto(id=photo_id, destination_id=destination.id,
        image_url=url, file_page_url=url, photographer=creator,
        license_name='AI generated · illustrative' if kind == 'ai_illustration' else 'Creator-authorized image',
        license_url='', alt_text=alt_text, media_kind=kind, is_primary=primary)
    db.add(photo)
    db.add(DestinationImageBlob(photo_id=photo_id, data=cleaned,
        content_type='image/jpeg', sha256=hashlib.sha256(cleaned).hexdigest()))
    db.add(AuditEvent(actor_id=admin.id, action='destination.media_uploaded',
        object_type='destination', object_id=destination.id, reason=f'{kind}: {creator}'[:300]))
    db.commit()
    return {'image_url':url, 'media_kind':kind, 'alt_text':alt_text}


@public_router.get('/{photo_id}')
def read_photo(photo_id: uuid.UUID, db: Session = Depends(get_db)):
    record = db.execute(select(DestinationImageBlob, DestinationPhoto, Destination)
        .join(DestinationPhoto, DestinationPhoto.id == DestinationImageBlob.photo_id)
        .join(Destination, Destination.id == DestinationPhoto.destination_id)
        .where(DestinationImageBlob.photo_id == photo_id,
               Destination.content_status.in_(['published', 'sample']))).first()
    if record is None:
        raise HTTPException(404, 'Image not found')
    blob, _photo, _destination = record
    return Response(blob.data, media_type=blob.content_type,
                    headers={'Cache-Control': 'public, max-age=86400', 'X-Content-Type-Options': 'nosniff'})
