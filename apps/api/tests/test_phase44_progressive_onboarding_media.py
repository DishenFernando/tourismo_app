"""Phase 4.4: low-friction onboarding and honest media provenance."""
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
import importlib.util
import uuid

import pytest
from fastapi import HTTPException, UploadFile
from fastapi.testclient import TestClient
from PIL import Image

from tourismo.main import app
from tourismo.admin import media
from tourismo.vendors.routes import VendorCreate, VendorEdit, submit_organization
from tourismo.core.models import DestinationImageBlob, DestinationPhoto, VendorOrganization
from tourismo.core.database import get_db


def jpg_image(size=(800, 450)) -> bytes:
    out = BytesIO()
    Image.new('RGB', size, (130, 180, 90)).save(out, 'JPEG')
    return out.getvalue()


def test_quick_draft_needs_just_three_fields_and_no_fake_location():
    draft = VendorCreate.model_validate({
        'category':'restaurant', 'business_name':'  Tea Garden Cafe  ',
        'contact_email':'TEAM@EXAMPLE.COM'})
    assert draft.business_name == 'Tea Garden Cafe'
    assert draft.contact_email == 'team@example.com'
    assert draft.province is None and draft.district is None
    assert draft.operating_address is None
    with pytest.raises(ValueError):
        VendorCreate.model_validate({'category':'restaurant','business_name':'',
                                     'contact_email':'team@example.com'})
    with pytest.raises(ValueError):
        VendorCreate.model_validate({'category':'restaurant','business_name':'Tea Garden Cafe',
                                     'contact_email':'bad-email'})
    assert VendorEdit.model_validate({'district':'Kandy'}).district == 'Kandy'


def test_incomplete_draft_cannot_be_submitted_even_with_license(monkeypatch):
    import tourismo.vendors.routes as routes
    user = SimpleNamespace(id=uuid.uuid4())
    org = VendorOrganization(id=uuid.uuid4(),owner_id=user.id, business_name='Test',
                             category='restaurant', contact_email='contact@example.com',
                             registration_no='REG123', province=None, district=None,
                             operating_address=None, verification_state='draft')
    monkeypatch.setattr(routes, '_organization', lambda *_args, **_kwargs: org)
    with pytest.raises(HTTPException) as exc:
        submit_organization(org.id, user, MagicMock())
    assert exc.value.status_code == 422
    assert 'province' in exc.value.detail


def test_image_sanitization_drops_metadata_and_shrinks_large_dimensions():
    original = jpg_image(size=(2400, 1600))
    result = media.sanitize_image(original)
    with Image.open(BytesIO(result)) as image:
        assert image.format == 'JPEG'
        assert max(image.size) <= 1920
        assert 'exif' not in image.info
    assert len(result) < media.MAX_UPLOAD_BYTES


def test_images_reject_wrong_bytes_excessive_size_and_svg():
    for payload in (b'<svg xmlns="http://www.w3.org/2000/svg"></svg>',
                    b'%%PDF-1.7', b'bad-image', b'x'*(media.MAX_UPLOAD_BYTES+1)):
        with pytest.raises(ValueError):
            media.sanitize_image(payload)


@pytest.mark.asyncio
async def test_admin_image_upload_requires_rights_and_provenance(monkeypatch):
    user = SimpleNamespace(id=uuid.uuid4())
    destination = SimpleNamespace(id=uuid.uuid4(),slug='kandy',photos=[])
    db = MagicMock()
    db.scalar.return_value = destination
    monkeypatch.setattr(media, 'get_settings', lambda: SimpleNamespace(app_environment='development'))
    content = jpg_image()
    def f():
        return UploadFile(filename='garden.jpg',file=BytesIO(content),headers={'content-type':'image/jpeg'})
    with pytest.raises(HTTPException) as exc:
        await media.upload_photo('kandy', f(), 'ai_illustration', 'Image engine',
                                 'Illustration of green hills', False, db, user)
    assert exc.value.status_code == 422
    result = await media.upload_photo('kandy', f(), 'ai_illustration', 'Image engine',
                                       'Illustration of green hills', True, db, user)
    assert result['media_kind'] == 'ai_illustration'
    added = [call.args[0] for call in db.add.call_args_list]
    photo = next(a for a in added if isinstance(a,DestinationPhoto))
    blob = next(a for a in added if isinstance(a,DestinationImageBlob))
    assert photo.media_kind == 'ai_illustration'
    assert 'illustrative' in photo.license_name.lower()
    assert blob.photo_id == photo.id and len(blob.sha256) == 64
    db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_production_fails_closed_for_db_image_upload(monkeypatch):
    monkeypatch.setattr(media, 'get_settings',lambda: SimpleNamespace(app_environment='production'))
    with pytest.raises(HTTPException) as exc:
        await media.upload_photo('galle',UploadFile(filename='test.jpg',file=BytesIO(jpg_image()),
             headers={'content-type':'image/jpeg'}),'owned_photo','Local author','Harbor view example',True,MagicMock(),SimpleNamespace(id=uuid.uuid4()))
    assert exc.value.status_code == 503


def test_public_media_not_visible_without_published_destination_and_admin_required():
    routes={route.path for route in app.routes}
    assert '/api/v1/admin/destinations/{slug}/photos/upload' in routes
    assert '/api/v1/destination-media/{photo_id}' in routes
    app.dependency_overrides[get_db] = lambda: MagicMock()
    try:
        with TestClient(app) as client:
            reply=client.post('/api/v1/admin/destinations/kandy/photos/upload')
            assert reply.status_code == 401
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_migration_is_additive_and_follows_discovery_indexes(monkeypatch):
    path=Path(__file__).parents[1]/'migrations'/'versions'/'0013_onboarding_media_ux.py'
    spec=importlib.util.spec_from_file_location('tourismo_phase44_migration',path)
    m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    assert m.down_revision == '0012_listing_discovery_indexes'
    changes=[]
    monkeypatch.setattr(m.op,'alter_column',lambda *args, **kwargs:changes.append(('alter',args[0],args[1])))
    monkeypatch.setattr(m.op,'add_column',lambda *args, **kwargs:changes.append(('add',args[0])))
    monkeypatch.setattr(m.op,'create_check_constraint',lambda *args, **kwargs:changes.append(('check',args[1])))
    monkeypatch.setattr(m.op,'create_table',lambda *args, **kwargs:changes.append(('table',args[0])))
    m.upgrade()
    assert ('table','destination_image_blobs') in changes
    assert sum(1 for x in changes if x[0]=='alter') == 3
