"""Phase 7.1: bounded photo normalization and fail-closed content moderation.

Text is public only after the moderation API returns a clean result. Suspected
text violations and moderation outages are held for admin review. Flagged photos
are rejected (not stored); on image-check outage the submission is rejected.
"""
import base64
from io import BytesIO
import json
import logging
import os
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import HTTPException
from PIL import Image, ImageOps, UnidentifiedImageError

log = logging.getLogger(__name__)
Image.MAX_IMAGE_PIXELS = 20_000_000
MAX_PHOTOS = 5
MAX_DATA_URI_LENGTH = 3_000_000  # ~2.25 MB before normalization
MAX_IMAGE_BYTES = 2_000_000
MAX_TOTAL_BYTES = 10_000_000
_ALLOWED = {'image/jpeg', 'image/png', 'image/webp'}
_DATA = re.compile(r'^data:(image/(?:jpeg|png|webp));base64,([A-Za-z0-9+/=\r\n]+)$')


def normalize_images(data_uris: list[str] | None) -> list[bytes]:
    if data_uris is None:
        return []
    if len(data_uris) > MAX_PHOTOS:
        raise HTTPException(422, 'Maximum five images per review')
    out: list[bytes] = []
    total = 0
    for uri in data_uris:
        if len(uri) > MAX_DATA_URI_LENGTH:
            raise HTTPException(422, 'Each image must be 2 MB or smaller')
        m = _DATA.fullmatch(uri)
        if m is None or m.group(1) not in _ALLOWED:
            raise HTTPException(422, 'Only JPEG, PNG and WebP photos are supported')
        try:
            raw = base64.b64decode(m.group(2), validate=True)
        except Exception as exc:
            raise HTTPException(422, 'Invalid image encoding') from exc
        if len(raw) > MAX_IMAGE_BYTES:
            raise HTTPException(422, 'Each image must be 2 MB or smaller')
        total += len(raw)
        if total > MAX_TOTAL_BYTES:
            raise HTTPException(422, 'Image upload size limit exceeded')
        try:
            # Verify the actual file, not merely the MIME indicated by the browser.
            with Image.open(BytesIO(raw)) as img:
                if img.format not in ('JPEG', 'PNG', 'WEBP'):
                    raise ValueError('Unsupported image signature')
                img.verify()
            with Image.open(BytesIO(raw)) as img:
                if img.width * img.height > Image.MAX_IMAGE_PIXELS:
                    raise ValueError('Image dimensions too large')
                clean = ImageOps.exif_transpose(img)
                clean.thumbnail((1280, 1280))
                # Produce a fresh RGB JPEG to discard EXIF and active image metadata.
                if clean.mode in ('RGBA', 'LA') or 'transparency' in clean.info:
                    rgba = clean.convert('RGBA')
                    bg = Image.new('RGB', rgba.size, 'white')
                    bg.paste(rgba, mask=rgba.getchannel('A'))
                    clean = bg
                else:
                    clean = clean.convert('RGB')
                buf = BytesIO()
                clean.save(buf, format='JPEG', quality=76, optimize=True)
                encoded = buf.getvalue()
                if len(encoded) > 1_000_000:
                    raise ValueError('Normalized image too large')
                out.append(encoded)
        except (UnidentifiedImageError, ValueError, OSError, Image.DecompressionBombError) as exc:
            raise HTTPException(422, 'Invalid or excessively large photo') from exc
    return out


def _scan(inputs: list[dict], token: str) -> bool:
    payload = json.dumps({'model': 'omni-moderation-latest', 'input': inputs}).encode('utf-8')
    req = Request('https://api.openai.com/v1/moderations', data=payload, headers={
        'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json',
    }, method='POST')
    with urlopen(req, timeout=15) as response:
        result = json.load(response)
    records = result.get('results', [])
    if not records or not all(isinstance(r.get('flagged'), bool) for r in records):
        raise ValueError('Invalid moderation response')
    return any(r['flagged'] for r in records)


def moderate_content(title: str, body: str, photos: list[bytes]) -> str:
    """False-positive text goes to admin; flagged images are prohibited.

    The text and photo screenings are separate, since a mixed flagged result
    would not distinguish a text issue from an image issue.
    """
    token = os.getenv('OPENAI_API_KEY', '').strip()
    if not token:
        if photos:
            raise HTTPException(503, 'Photo moderation unavailable; images cannot be accepted safely')
        return 'pending'
    try:
        needs_text_review = _scan([{'type': 'text', 'text': title + '\n' + body}], token)
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, KeyError) as exc:
        log.warning('Review text moderation unavailable (%s)', type(exc).__name__)
        needs_text_review = True
    if photos:
        try:
            # A single mixed request covers all five images; a flagged result
            # rejects the entire set so no prohibited image reaches storage.
            image_items = [{'type': 'image_url', 'image_url': {
                'url': 'data:image/jpeg;base64,' + base64.b64encode(data).decode('ascii'),
            }} for data in photos]
            if _scan(image_items, token):
                raise HTTPException(422, 'One or more photos violated the image policy; remove or replace them')
        except HTTPException:
            raise
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, KeyError) as exc:
            log.warning('Review image moderation unavailable (%s)', type(exc).__name__)
            raise HTTPException(503, 'Image safety check unavailable; please retry later') from exc
    return 'pending' if needs_text_review else 'published'
