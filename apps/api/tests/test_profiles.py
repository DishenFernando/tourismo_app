"""No real Clerk account or password is needed to test profile authorization."""
import uuid

from fastapi.testclient import TestClient
from tourismo.core.database import get_db
from tourismo.core.models import User
from tourismo.identity.security import require_user
from tourismo.identity.profile import ProfileUpdate, fetch_clerk_identity
from tourismo.main import app

client = TestClient(app)


def test_profile_requires_verified_session():
    assert client.get('/api/v1/me').status_code == 401
    assert client.post('/api/v1/auth/session/bootstrap').status_code == 401
    assert client.patch('/api/v1/me', json={'display_name': 'Traveler'}).status_code == 401


def test_profile_input_only_accepts_safe_fields():
    good = ProfileUpdate(display_name='  Tourismo Traveler  ', locale='si', home_region=' Kandy ')
    assert good.display_name == 'Tourismo Traveler'
    assert good.home_region == 'Kandy'
    assert good.locale == 'si'
    invalid = {'display_name': 'Traveler', 'status': 'superadmin', 'roles': ['admin'], 'email': 'forged@example.com'}
    response = client.patch('/api/v1/me', json=invalid)
    assert response.status_code == 401  # No identity; protected even before validating input.
    try:
        ProfileUpdate.model_validate(invalid)
    except ValueError:
        pass
    else:
        raise AssertionError('Privilege, email, and role changes must not be accepted')


def test_profile_edit_does_not_modify_identity_or_roles():
    user = User(id=uuid.uuid4(), auth_subject='test-verified-user', display_name=None,
                email='verified@example.com', locale='en', status='active',
                home_region=None, bio=None, profile_completed_at=None)

    class FakeDb:
        def commit(self):
            pass
        def refresh(self, _):
            pass

    app.dependency_overrides[require_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: FakeDb()
    try:
        edited = client.patch('/api/v1/me', json={'display_name': '  Maya  ', 'locale': 'ta',
                                                  'home_region': '  Kandy ', 'bio': 'Nature trips'})
        assert edited.status_code == 200
        record = edited.json()
        assert record['display_name'] == 'Maya'
        assert record['home_region'] == 'Kandy'
        assert record['locale'] == 'ta'
        assert record['profile_completed'] is True
        assert record['email'] == 'verified@example.com'
        assert record['roles'] == ['tourist']
        assert user.auth_subject == 'test-verified-user'
        assert client.patch('/api/v1/me', json={'display_name':'Change', 'status':'active'}).status_code == 422
        assert client.get('/api/v1/me').json()['display_name'] == 'Maya'
    finally:
        app.dependency_overrides.clear()


def test_clerk_profile_is_optional_without_backend_key(monkeypatch):
    class Settings:
        clerk_secret_key = ''
    monkeypatch.setattr('tourismo.identity.profile.get_settings', lambda: Settings())
    assert fetch_clerk_identity('user_clerk') is None


def test_clerk_sync_uses_verified_primary_email_only(monkeypatch):
    class Settings:
        clerk_secret_key = 'sk_test_placeholder'
    monkeypatch.setattr('tourismo.identity.profile.get_settings', lambda: Settings())

    class Response:
        def raise_for_status(self):
            pass
        def json(self):
            return {'id':'user_clerk','primary_email_address_id':'a',
                    'first_name':'Maya','last_name':'Perera',
                    'email_addresses':[{'id':'a','email_address':'maya@example.com',
                                        'verification':{'status':'verified'}},
                                       {'id':'b','email_address':'unverified@example.com',
                                        'verification':{'status':'unverified'}}]}

    def fake_get(url, headers, timeout):
        assert url == 'https://api.clerk.com/v1/users/user_clerk'
        assert headers['Authorization'] == 'Bearer sk_test_placeholder'
        assert timeout == 4.0
        return Response()

    monkeypatch.setattr('tourismo.identity.profile.httpx.get', fake_get)
    assert fetch_clerk_identity('user_clerk') == ('maya@example.com', 'Maya Perera')
