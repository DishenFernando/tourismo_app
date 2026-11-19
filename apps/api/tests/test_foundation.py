from fastapi.testclient import TestClient
from tourismo.main import app

client = TestClient(app)


def sample_trip():
    return {
        'destination_slug': 'nuwara-eliya', 'title': 'Six friends in Nuwara Eliya',
        'adults': 6, 'children_ages': [], 'budget_limit_minor': 9000000,
        'budget_items': [
            {'category': 'accommodation', 'minimum_minor': 2000000, 'expected_minor': 3000000, 'maximum_minor': 4000000},
            {'category': 'transport', 'minimum_minor': 1000000, 'expected_minor': 2000000, 'maximum_minor': 3000000},
        ],
    }


def test_public_no_account_or_db():
    assert client.get('/api/v1/health/live').json() == {'status': 'ok'}
    assert client.get('/api/v1/auth/config').status_code == 200
    response = client.post('/api/v1/trips/preview', json=sample_trip())
    assert response.status_code == 200
    assert response.json()['expected_minor'] == 5_000_000
    assert response.json()['maximum_minor'] == 7_000_000


def test_cloud_trip_requires_login():
    assert client.post('/api/v1/trips', json=sample_trip()).status_code == 401
    assert client.get('/api/v1/trips').status_code == 401
    assert client.get('/api/v1/me').status_code == 401


def test_child_ages_not_negative():
    bad = sample_trip()
    bad['children_ages'] = [8, -1]
    assert client.post('/api/v1/trips/preview', json=bad).status_code == 422


def test_group_capacity_and_date_checks():
    bad = sample_trip()
    bad.update({'adults': 30, 'children_ages': [1] * 11})
    assert client.post('/api/v1/trips/preview', json=bad).status_code == 422
    bad = sample_trip()
    bad.update({'start_date': '2027-02-03', 'end_date': '2027-02-01'})
    assert client.post('/api/v1/trips/preview', json=bad).status_code == 422


def test_budget_min_expected_max_order():
    bad = sample_trip()
    bad['budget_items'][0]['minimum_minor'] = 6000000
    assert client.post('/api/v1/trips/preview', json=bad).status_code == 422


def test_budget_cap_flags_upper_bound():
    data = sample_trip()
    data['budget_limit_minor'] = 6_000_000
    response = client.post('/api/v1/trips/preview', json=data)
    assert response.json()['exceeds_limit'] is True
    assert response.json()['remaining_minor'] == 1_000_000


def test_no_unconfigured_sms_simulation():
    assert client.get('/api/v1/auth/config').json()['phone_otp_enabled'] is False


def test_guest_preview_does_not_create_saved_trip():
    # There is intentionally no DB dependency in preview; this succeeds without PostgreSQL.
    assert client.post('/api/v1/trips/preview', json=sample_trip()).status_code == 200


def test_invalid_bearer_rejected_when_unconfigured():
    assert client.get('/api/v1/me', headers={'Authorization': 'Bearer not-a-jwt'}).status_code in (401, 503)
