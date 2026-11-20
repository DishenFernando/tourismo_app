"""Phase 4.5 Part 2 regressions: trusted invitations and safe listing media."""
import hashlib
from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import ValidationError

from tourismo.main import app
from tourismo.listings.routes import PhotoWrite
from tourismo.listings import media
from tourismo.vendors import routes as vendors


def test_email_invite_schema_requires_email_not_user_uuid():
    invite = vendors.MemberEmailInvite.model_validate({'email': '  Person@Example.COM ', 'role': 'staff'})
    assert invite.email == 'person@example.com'
    for bad in ({'email': 'x', 'role': 'staff'}, {'email': 'x@example.com', 'role': 'owner'},
                {'email': 'x@example.com', 'role': 'staff', 'user_id': str(uuid4())}):
        with pytest.raises(ValidationError):
            vendors.MemberEmailInvite.model_validate(bad)


def test_email_invite_requires_an_existing_verified_local_account(monkeypatch):
    user = SimpleNamespace(id=uuid4())
    monkeypatch.setattr(vendors, '_organization', lambda *args: SimpleNamespace(id=args[1]))
    db = Mock()
    db.scalars.return_value.all.return_value = []
    with pytest.raises(HTTPException) as exc:
        vendors.invite_member_by_email(uuid4(), vendors.MemberEmailInvite(email='new@example.com', role='staff'), user, db)
    assert exc.value.status_code == 404


def test_email_invite_resolves_clerk_backed_user_only(monkeypatch):
    owner = SimpleNamespace(id=uuid4())
    invitee = SimpleNamespace(id=uuid4(), email='staff@example.com', auth_subject='user_genuine_clerk_subject')
    monkeypatch.setattr(vendors, '_organization', lambda *args: SimpleNamespace(id=args[1]))
    db = Mock()
    db.scalars.return_value.all.return_value = [invitee]
    called = {}
    def record_invite(org_id, body, user, session):
        called.update(invitee_id=body.user_id, role=body.role)
        return {'state': 'pending'}
    monkeypatch.setattr(vendors, 'invite_member', record_invite)
    answer = vendors.invite_member_by_email(uuid4(), vendors.MemberEmailInvite(
        email='Staff@Example.com', role='manager'), owner, db)
    assert answer['state'] == 'pending'
    assert called == {'invitee_id': invitee.id, 'role': 'manager'}
    db.scalars.return_value.all.return_value = [SimpleNamespace(id=uuid4(), auth_subject='demo_placeholder')]
    with pytest.raises(HTTPException) as exc:
        vendors.invite_member_by_email(uuid4(), vendors.MemberEmailInvite(
            email='staff@example.com', role='staff'), owner, db)
    assert exc.value.status_code == 404


def test_photo_write_accepts_exact_local_route_but_not_fake_url():
    photo_id = str(uuid4())
    media_url = f'/api/v1/listing-media/{photo_id}'
    payload = {'image_url': media_url, 'source_url': media_url, 'credit': 'Business owner',
               'license_name': 'Creator-authorized photograph', 'license_url': '',
               'alt_text': 'Real photo of a hotel room'}
    assert PhotoWrite.model_validate(payload).source_url == media_url
    for invalid in ('/api/v1/listing-media/nope', '//example.com/image.jpg', 'http://localhost:8000/image.jpg'):
        with pytest.raises(ValidationError):
            PhotoWrite.model_validate({**payload, 'image_url': invalid})


def test_media_production_uploads_are_blocked(monkeypatch):
    monkeypatch.setattr(media, 'get_settings', lambda: SimpleNamespace(app_environment='production'))
    with pytest.raises(HTTPException) as exc:
        media.require_development_media()
    assert exc.value.status_code == 503


def test_photo_publication_requires_existing_approved_listing(monkeypatch):
    blob = SimpleNamespace(data=b'test', sha256=hashlib.sha256(b'test').hexdigest())
    photo = SimpleNamespace(listing_id=uuid4())
    db = Mock()
    db.execute.return_value.first.return_value = (blob, photo)
    db.scalar.return_value = None  # Public search gate rejected unpublished or unverified listing.
    with pytest.raises(HTTPException) as exc:
        media.read_listing_photo(uuid4(), db)
    assert exc.value.status_code == 404


def test_photo_publication_returns_sanitized_bytes_when_approved():
    content = b'photo-bytes'
    blob = SimpleNamespace(data=content, sha256=hashlib.sha256(content).hexdigest())
    photo = SimpleNamespace(listing_id=uuid4())
    db = Mock()
    db.execute.return_value.first.return_value = (blob, photo)
    db.scalar.return_value = SimpleNamespace(id=photo.listing_id)
    response = media.read_listing_photo(uuid4(), db)
    assert response.body == content
    assert response.headers['x-content-type-options'] == 'nosniff'
    db.scalar.return_value = None


def test_private_preview_rejects_wrong_listing_photo(monkeypatch):
    monkeypatch.setattr(media, '_member_listing', lambda *args: (None, None))
    db = Mock()
    db.execute.return_value.first.return_value = None
    with pytest.raises(HTTPException) as exc:
        media.preview_listing_photo(uuid4(), uuid4(), uuid4(), SimpleNamespace(id=uuid4()), db)
    assert exc.value.status_code == 404


def test_sanitize_local_service_photo_strips_exif():
    image = Image.new('RGB', (24, 24), (130, 160, 190))
    out = BytesIO()
    image.save(out, format='JPEG', exif=b'Exif\x00\x00secret-opaque-location')
    from tourismo.admin.media import sanitize_image
    safe = sanitize_image(out.getvalue())
    assert safe.startswith(b'\xff\xd8')
    assert b'secret-opaque-location' not in safe


def test_private_media_endpoints_reject_unauthenticated_access():
    client = TestClient(app)
    org, listing, photo = uuid4(), uuid4(), uuid4()
    for endpoint in (
        f'/api/v1/vendor/organizations/{org}/listings/{listing}/photos/upload',
        f'/api/v1/vendor/organizations/{org}/listings/{listing}/photos/{photo}/preview',
        f'/api/v1/vendor/organizations/{org}/members/by-email',
    ):
        response = client.post(endpoint) if endpoint.endswith(('upload', 'by-email')) else client.get(endpoint)
        assert response.status_code in (401, 422)
