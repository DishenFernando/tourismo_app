"""Phase 5.3: stable public place references and no private-map leakage."""
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.dialects.postgresql import dialect

from tourismo.core.database import get_db
from tourismo.main import app
from tourismo.maps.place_ids import parse_place_id
from tourismo.maps.routes import _itinerary_public_places
from tourismo.trips.schemas import Stop, TripDraft
from tourismo.trips.routes import to_saved


def sample_trip(place_id=None):
    item = {'day': 1, 'title': 'Kandy walk', 'note': 'Bring water'}
    if place_id is not None:
        item['place_id'] = place_id
    return {'destination_slug': 'kandy', 'title': 'A weekend in Kandy', 'adults': 2,
            'itinerary': [item], 'budget_items': []}


def test_existing_manual_stops_remain_backward_compatible():
    assert Stop(day=1, title='Morning walk').place_id is None
    trip = TripDraft.model_validate(sample_trip())
    assert trip.model_dump(mode='json')['itinerary'][0]['place_id'] is None
    assert trip.itinerary[0].note == 'Bring water'


def test_stable_references_roundtrip_on_guest_preview():
    place_id = f'attraction:{uuid4()}'
    draft = TripDraft.model_validate(sample_trip(place_id))
    assert draft.itinerary[0].place_id == place_id
    with TestClient(app) as client:
        response = client.post('/api/v1/trips/preview', json=draft.model_dump(mode='json'))
        assert response.status_code == 200
        assert response.json()['expected_minor'] == 0
        assert client.post('/api/v1/trips', json=draft.model_dump(mode='json')).status_code == 401


@pytest.mark.parametrize('value', [
    'service:123', 'vendor:00000000-0000-0000-0000-000000000000',
    'service:not-a-uuid', 'service:00000000-0000-0000-0000-00000000000z',
    '../admin', 'service:00000000000000000000000000000000',
    'SERVICE:00000000-0000-0000-0000-000000000000',
    'service:AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA',
])
def test_bad_public_reference_rejected_in_trip(value):
    with pytest.raises((ValueError, ValidationError)):
        TripDraft.model_validate(sample_trip(value))


def test_query_endpoint_rejects_invalid_or_excessive_references():
    db = Mock()
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            for item in ([], ['service:garbage'], ['bad'], ['a']*91):
                response = client.post('/api/v1/map/itinerary-places', json={'place_ids':item})
                assert response.status_code == 422, response.text
                db.execute.assert_not_called()
                db.scalars.assert_not_called()
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_missing_or_unpublished_points_are_omitted_without_fake_coordinates():
    db = Mock()
    db.execute.return_value.all.return_value = []
    db.scalars.return_value.all.return_value = []
    ids = [f'destination:{uuid4()}', f'attraction:{uuid4()}', f'service:{uuid4()}']
    resolved = _itinerary_public_places(db, ids)
    assert resolved == []


def test_public_queries_reuse_service_visibility_and_editorial_status():
    db = Mock()
    queries = []
    def capture(stmt):
        queries.append(str(stmt.compile(dialect=dialect(), compile_kwargs={'literal_binds':True})))
        return SimpleNamespace(all=lambda: [])
    db.execute.side_effect = capture
    def services(stmt):
        queries.append(str(stmt.compile(dialect=dialect(), compile_kwargs={'literal_binds':True})))
        return SimpleNamespace(all=lambda: [])
    db.scalars.side_effect = services
    _itinerary_public_places(db,[f'destination:{uuid4()}', f'attraction:{uuid4()}', f'service:{uuid4()}'])
    assert len(queries) == 3
    assert all('WHERE' in sql for sql in queries)
    assert 'content_status' in queries[0] and 'location IS NOT NULL' in queries[0]
    assert 'content_status' in queries[1] and 'latitude IS NOT NULL' in queries[1]
    assert 'published' in queries[2] and 'rejected' in queries[2]
    assert 'expired_license' in queries[2] and 'vendor_evidence' in queries[2]
    assert 'demo' not in '\n'.join(queries).lower()


def test_service_badge_derives_only_from_current_public_org_state():
    id1, id2 = uuid4(), uuid4()
    verified = SimpleNamespace(id=id1, title='Approved stay', slug='approved-stay', category='accommodation',
        district='Kandy', latitude=7.28, longitude=80.63, location_note=None, location_source_url=None,
        organization=SimpleNamespace(verification_state='approved'))
    unverified = SimpleNamespace(id=id2, title='Regular stay', slug='regular-stay', category='accommodation',
        district='Kandy', latitude=7.29, longitude=80.64, location_note=None, location_source_url=None,
        organization=SimpleNamespace(verification_state='draft'))
    db = Mock()
    db.scalars.return_value.all.return_value = [unverified, verified]
    ids = [f'service:{id1}', f'service:{id2}']
    points = _itinerary_public_places(db, ids)
    assert [p.id for p in points] == ids
    assert [p.business_verified for p in points] == [True, False]
    assert all('email' not in p.model_dump() for p in points)


def test_existing_saved_trip_retains_stored_reference_without_revealing_vendor_data():
    ref = f'service:{uuid4()}'
    draft = TripDraft.model_validate(sample_trip(ref))
    fields = draft.model_dump(mode='json')
    row = SimpleNamespace(id=uuid4(), client_draft_id=draft.client_draft_id,
        destination_slug=draft.destination_slug, title=draft.title, start_date=draft.start_date,
        end_date=draft.end_date, adults=draft.adults, children_ages=draft.children_ages,
        budget_limit_minor=draft.budget_limit_minor, budget_flexible=draft.budget_flexible,
        budget_items=fields['budget_items'], itinerary=fields['itinerary'])
    result = to_saved(row)
    assert result.draft.itinerary[0].place_id == ref
    assert result.preview.expected_minor == 0
