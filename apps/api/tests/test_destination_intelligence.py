"""Phase 2.1 API response and migration contract tests (no live database required)."""
from pathlib import Path
from types import SimpleNamespace
import importlib.util
import uuid
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect
from tourismo.main import app
from tourismo.core.database import Base, get_db
from tourismo.core.models import DestinationGuide, PointOfInterest, PoiTranslation
from tourismo.geography import routes


class _ScalarResults:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class FakeDB:
    def __init__(self, destination, rows):
        self.destination = destination
        self.rows = rows

    def scalar(self, _statement):
        return self.destination

    def scalars(self, _statement):
        return _ScalarResults(self.rows)


def _source():
    return SimpleNamespace(name='UNESCO World Heritage Centre', url='https://whc.unesco.org/en/list/451/',
                           license_status='reference_link_only', verified_at=None)


def test_model_tables_and_uniqueness():
    assert {'destination_guides', 'poi', 'poi_translations'}.issubset(Base.metadata.tables)
    assert inspect(DestinationGuide).primary_key
    assert inspect(PointOfInterest).primary_key
    assert inspect(PoiTranslation).primary_key
    assert any(c.name == 'uq_poi_destination_slug' for c in PointOfInterest.__table__.constraints)


def test_english_fallback_for_untranslated_guide():
    destination = SimpleNamespace(id=uuid.uuid4())
    guide = SimpleNamespace(locale='en', overview='Heritage guide', highlights=['Historic fort'],
                            local_tips=[], content_status='sample', verified_at=None, source=_source())
    response = routes.destination_guide('galle', 'si', FakeDB(destination, [guide]))
    assert response.fallback_used is True
    assert response.locale == 'en'
    assert response.source.url == 'https://whc.unesco.org/en/list/451/'
    assert response.content_status == 'sample'


def test_poi_translation_fallback_and_source():
    destination = SimpleNamespace(id=uuid.uuid4())
    translation = SimpleNamespace(locale='en', title='Galle Fort', description='Historic town', local_tips='')
    poi = SimpleNamespace(slug='old-town-galle-fort', category='heritage', translations=[translation],
                          content_status='sample', verified_at=None, source=_source())
    response = routes.destination_pois('galle', 'ta', None, FakeDB(destination, [poi]))
    assert response[0].fallback_used is True
    assert response[0].source.name == 'UNESCO World Heritage Centre'
    assert response[0].title == 'Galle Fort'


def test_no_editorial_guide_returns_404():
    with pytest.raises(HTTPException) as exc:
        routes.destination_guide('ella', 'en', FakeDB(SimpleNamespace(id=uuid.uuid4()), []))
    assert exc.value.status_code == 404


def test_invalid_locale_and_category_are_rejected():
    app.dependency_overrides[get_db] = lambda: object()
    try:
        with TestClient(app) as client:
            assert client.get('/api/v1/destinations/galle/guide?locale=fr').status_code == 422
            assert client.get('/api/v1/destinations/galle/pois?category=FAKE;DROP').status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_migration_seeds_five_source_link_only_samples(monkeypatch):
    migration = Path(__file__).parents[1] / 'migrations' / 'versions' / '0003_destination_intelligence.py'
    spec = importlib.util.spec_from_file_location('phase2_destination_migration', migration)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    statements = []
    monkeypatch.setattr(mod.op, 'execute', lambda stmt: statements.append(stmt))
    monkeypatch.setattr(mod.op, 'create_table', lambda *a, **kw: None)
    monkeypatch.setattr(mod.op, 'create_index', lambda *a, **kw: None)
    mod.upgrade()
    assert len(mod.SAMPLES) == 5
    assert len(statements) == 20  # Source, guide, POI, POI translation per destination
    sql = '\n'.join(str(stmt.compile(dialect=postgresql.dialect())) for stmt in statements)
    assert 'CAST(' in sql and 'AS UUID)' in sql
    assert "'sample'" in sql
    assert "reference_link_only" in sql
    assert "ON CONFLICT" in sql
    assert "'published'" not in sql
