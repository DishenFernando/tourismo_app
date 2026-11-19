"""Integration against a disposable PostGIS database migrated to Alembic head.

Run after creating a dedicated test database and applying migrations:
TEST_DATABASE_URL=postgresql+psycopg://... pytest -q tests/test_destination_intelligence_postgres.py
"""
import os
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from tourismo.core.database import get_db
from tourismo.core.models import Destination, PointOfInterest, PoiTranslation
from tourismo.main import app


@pytest.mark.skipif(not os.environ.get('TEST_DATABASE_URL'), reason='Requires migrated disposable PostGIS test database')
def test_public_guides_provenance_fallback_and_draft_isolation():
    engine = create_engine(os.environ['TEST_DATABASE_URL'])

    def test_db():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = test_db
    try:
        with TestClient(app) as client:
            for slug in ('anuradhapura', 'galle', 'kandy', 'nuwara-eliya', 'ella'):
                guide = client.get(f'/api/v1/destinations/{slug}/guide')
                assert guide.status_code == 200, guide.text
                assert guide.json()['content_status'] == 'sample'
                assert guide.json()['source']['url'].startswith('https://')
                assert guide.json()['verified_at'] is None
                poi = client.get(f'/api/v1/destinations/{slug}/pois')
                assert poi.status_code == 200, poi.text
                assert len(poi.json()) >= 1
                assert poi.json()[0]['source']['url'].startswith('https://')

            tamil = client.get('/api/v1/destinations/galle/guide?locale=ta')
            assert tamil.json()['locale'] == 'en'
            assert tamil.json()['fallback_used'] is True
            assert client.get('/api/v1/destinations/does-not-exist/guide').status_code == 404
            assert client.get('/api/v1/destinations/galle/pois?category=nature').json() == []

            draft_slug = 'hidden-for-test-' + uuid.uuid4().hex[:12]
            with Session(engine) as session:
                d = session.scalar(select(Destination).where(Destination.slug == 'galle'))
                draft = PointOfInterest(destination_id=d.id, slug=draft_slug,
                                        category='heritage', content_status='draft')
                session.add(draft)
                session.flush()
                session.add(PoiTranslation(poi_id=draft.id, locale='en',
                                           title='Unpublished', description='Not public'))
                session.commit()
            try:
                public = client.get('/api/v1/destinations/galle/pois').json()
                assert all(p['slug'] != draft_slug for p in public)
            finally:
                with Session(engine) as session:
                    hidden = session.scalar(select(PointOfInterest).where(PointOfInterest.slug == draft_slug))
                    if hidden:
                        session.delete(hidden)
                        session.commit()
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
