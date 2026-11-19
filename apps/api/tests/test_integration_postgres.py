"""Run with TEST_DATABASE_URL after applying migrations against a disposable test database."""
import os
import pytest
from fastapi.testclient import TestClient
from tourismo.main import app


@pytest.mark.skipif(not os.environ.get('TEST_DATABASE_URL'), reason='Requires disposable migrated PostgreSQL test database')
def test_destinations_read_database():
    from tourismo.core.database import get_db
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    engine = create_engine(os.environ['TEST_DATABASE_URL'])
    def test_db():
        with Session(engine) as session:
            yield session
    app.dependency_overrides[get_db] = test_db
    try:
        with TestClient(app) as client:
            response = client.get('/api/v1/destinations?q=Nuwara')
            assert response.status_code == 200
            assert response.json()[0]['slug'] == 'nuwara-eliya'
            assert response.json()[0]['is_sample'] is True
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


@pytest.mark.skipif(not os.environ.get('TEST_DATABASE_URL'), reason='Requires disposable migrated PostgreSQL test database')
def test_private_trip_owned_by_current_user():
    """Two distinct provider-verified subjects are modeled by a test-only dependency override."""
    import uuid
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from tourismo.core.database import get_db
    from tourismo.core.models import User
    from tourismo.identity.security import require_user

    engine = create_engine(os.environ['TEST_DATABASE_URL'])
    user_a = User(auth_subject=f'test-A-{uuid.uuid4().hex}', status='active')
    user_b = User(auth_subject=f'test-B-{uuid.uuid4().hex}', status='active')
    with Session(engine) as db:
        db.add_all([user_a, user_b]); db.commit()

    def test_db():
        with Session(engine) as session:
            yield session
    app.dependency_overrides[get_db] = test_db
    app.dependency_overrides[require_user] = lambda: user_a
    payload = {'client_draft_id': str(uuid.uuid4()), 'destination_slug': 'nuwara-eliya', 'title': 'Private test trip', 'adults': 2, 'children_ages': [], 'budget_items': []}
    try:
        with TestClient(app) as client:
            created = client.post('/api/v1/trips', json=payload)
            assert created.status_code == 201
            trip_id = created.json()['id']
            # Same client's repeated confirmation is idempotent.
            assert client.post('/api/v1/trips', json=payload).json()['id'] == trip_id
            assert client.get(f'/api/v1/trips/{trip_id}').status_code == 200
            app.dependency_overrides[require_user] = lambda: user_b
            assert client.get(f'/api/v1/trips/{trip_id}').status_code == 404
            assert all(t['id'] != trip_id for t in client.get('/api/v1/trips').json())
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
