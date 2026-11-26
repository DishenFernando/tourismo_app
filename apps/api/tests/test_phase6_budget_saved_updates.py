"""Phase 6: budget arithmetic, versioned owner edits, and guest access protections."""
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.dialects.postgresql import dialect

from tourismo.core.database import get_db
from tourismo.identity.security import require_user
from tourismo.main import app
from tourismo.trips.routes import to_saved
from tourismo.trips.schemas import TripDraft, calculate_preview


def example(**extra):
    draft = {'destination_slug':'kandy', 'title':'Budget Kandy holiday', 'adults':2,
             'children_ages':[8], 'budget_limit_minor':30_000,
             'itinerary':[{'day':1,'title':'Visit the lake'}],
             'budget_items':[
                 {'category':'food','description':'Lunch','day':1,'minimum_minor':1000,
                  'expected_minor':2000,'maximum_minor':4000},
                 {'category':'food','description':'Dinner','day':1,'minimum_minor':2000,
                  'expected_minor':3000,'maximum_minor':6000},
                 {'category':'transport','description':'Taxi','day':2,'minimum_minor':5000,
                  'expected_minor':8000,'maximum_minor':13000},
                 {'category':'misc','description':'Whole trip','minimum_minor':100,
                  'expected_minor':200,'maximum_minor':300}
             ]}
    draft.update(extra)
    return draft


def row_from_draft(draft, owner, version=1, id=None):
    return SimpleNamespace(id=id or uuid4(),owner_id=owner,version=version,
        client_draft_id=draft.client_draft_id,destination_slug=draft.destination_slug,
        title=draft.title,start_date=draft.start_date,end_date=draft.end_date,
        adults=draft.adults,children_ages=draft.children_ages,budget_limit_minor=draft.budget_limit_minor,
        budget_flexible=draft.budget_flexible,
        budget_items=draft.model_dump(mode='json')['budget_items'],
        itinerary=draft.model_dump(mode='json')['itinerary'])


def test_day_and_category_breakdown_is_exact_and_backwards_compatible():
    d = TripDraft.model_validate(example())
    preview = calculate_preview(d)
    assert (preview.minimum_minor,preview.expected_minor,preview.maximum_minor)==(8100,13200,23300)
    assert preview.per_traveler_expected_minor == 4400
    assert [(s.category,s.expected_minor) for s in preview.by_category] == [
        ('food',5000),('transport',8000),('misc',200)]
    assert [(s.day,s.expected_minor) for s in preview.by_day] == [(1,5000),(2,8000)]
    assert preview.unassigned.expected_minor==200
    assert preview.remaining_minor==16800
    assert not preview.exceeds_limit
    legacy = TripDraft.model_validate(example(budget_items=[{'category':'food','minimum_minor':5,
                                                               'expected_minor':10,'maximum_minor':25}]))
    assert legacy.budget_items[0].day is None
    assert calculate_preview(legacy).unassigned.expected_minor == 10


def test_budget_validation_and_edge_cases():
    for invalid in (
        {'category':'food','day':0,'minimum_minor':1,'expected_minor':1,'maximum_minor':2},
        {'category':'food','day':32,'minimum_minor':1,'expected_minor':1,'maximum_minor':2},
        {'category':'food','minimum_minor':300,'expected_minor':200,'maximum_minor':400},
        {'category':'food','minimum_minor':300,'expected_minor':400,'maximum_minor':200},
        {'category':'food','minimum_minor':-1,'expected_minor':2,'maximum_minor':3},
    ):
        with pytest.raises(ValidationError):
            TripDraft.model_validate(example(budget_items=[invalid]))
    with pytest.raises(ValidationError):
        TripDraft.model_validate(example(budget_items=example()['budget_items']*21))


def test_guest_cannot_read_update_or_delete_saved_trips():
    identifier=str(uuid4())
    with TestClient(app) as client:
        assert client.get('/api/v1/trips/'+identifier).status_code==401
        assert client.patch('/api/v1/trips/'+identifier,json={'expected_version':1,'draft':example()}).status_code==401
        assert client.delete('/api/v1/trips/'+identifier).status_code==401


def test_versioned_update_compiles_owner_and_version_cas_and_returns_next_version():
    owner=SimpleNamespace(id=uuid4())
    draft=TripDraft.model_validate(example())
    previous=row_from_draft(draft, owner.id, version=4)
    db=Mock()
    def refresh(row):
        row.version = 5
    db.refresh.side_effect=refresh
    queries=[]
    replies=iter([previous, previous.id])
    def scalar(stmt):
        queries.append(stmt)
        return next(replies)
    db.scalar.side_effect=scalar
    app.dependency_overrides[get_db]=lambda:db
    app.dependency_overrides[require_user]=lambda:owner
    try:
        with TestClient(app) as client:
            response=client.patch(f'/api/v1/trips/{previous.id}',json={
                'expected_version':4,'draft':draft.model_dump(mode='json')})
        assert response.status_code==200,response.text
        assert response.json()['version']==5
        assert response.json()['preview']['by_day'][0]['day']==1
        assert db.commit.call_count==1
        assert len(queries)==2
        db.refresh.assert_called_once_with(previous)
        compiled=queries[1].compile(dialect=dialect())
        sql=str(compiled)
        assert 4 in compiled.params.values()
        assert owner.id in compiled.params.values()
        assert 'version + ' in sql
        assert 'client_draft_id =' not in sql
    finally:
        app.dependency_overrides.clear()


def test_stale_version_is_rejected_without_write():
    owner=SimpleNamespace(id=uuid4())
    draft=TripDraft.model_validate(example())
    old=row_from_draft(draft,owner.id,version=3)
    db=Mock()
    db.scalar.return_value=old
    app.dependency_overrides[get_db]=lambda:db
    app.dependency_overrides[require_user]=lambda:owner
    try:
        with TestClient(app) as client:
            response=client.patch(f'/api/v1/trips/{old.id}',json={'expected_version':2,'draft':draft.model_dump(mode='json')})
        assert response.status_code==409
        assert db.scalar.call_count==1
        db.commit.assert_not_called()
    finally:
        app.dependency_overrides.clear()


def test_racing_update_is_rejected_and_rolled_back():
    owner=SimpleNamespace(id=uuid4())
    draft=TripDraft.model_validate(example())
    old=row_from_draft(draft,owner.id,version=3)
    db=Mock()
    db.scalar.side_effect=[old,None]
    app.dependency_overrides[get_db]=lambda:db
    app.dependency_overrides[require_user]=lambda:owner
    try:
        with TestClient(app) as client:
            response=client.patch(f'/api/v1/trips/{old.id}',json={'expected_version':3,'draft':draft.model_dump(mode='json')})
        assert response.status_code==409
        db.rollback.assert_called_once()
        db.commit.assert_not_called()
    finally:
        app.dependency_overrides.clear()


def test_wrong_owner_has_no_update_or_delete():
    owner=SimpleNamespace(id=uuid4())
    draft=TripDraft.model_validate(example())
    db=Mock()
    db.scalar.return_value=None
    app.dependency_overrides[get_db]=lambda:db
    app.dependency_overrides[require_user]=lambda:owner
    try:
        with TestClient(app) as client:
            edit=client.patch(f'/api/v1/trips/{uuid4()}',json={'expected_version':1,'draft':draft.model_dump(mode='json')})
            deletion=client.delete(f'/api/v1/trips/{uuid4()}')
        assert edit.status_code==404
        assert deletion.status_code==404
        db.commit.assert_not_called()
    finally:
        app.dependency_overrides.clear()


def test_delete_only_owner_trip():
    owner=SimpleNamespace(id=uuid4())
    trip_id=uuid4()
    db=Mock()
    db.scalar.return_value=trip_id
    app.dependency_overrides[get_db]=lambda:db
    app.dependency_overrides[require_user]=lambda:owner
    try:
        with TestClient(app) as client:
            response=client.delete(f'/api/v1/trips/{trip_id}')
        assert response.status_code==204
        sql=str(db.scalar.call_args[0][0].compile(dialect=dialect(),compile_kwargs={'literal_binds':True}))
        assert 'DELETE FROM trips' in sql and str(owner.id) in sql and str(trip_id) in sql
        db.commit.assert_called_once()
    finally:
        app.dependency_overrides.clear()
