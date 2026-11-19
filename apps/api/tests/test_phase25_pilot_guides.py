"""Editorial seed safety and regression tests; no PostgreSQL required."""
import importlib.util
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql

from tourismo.geography.pilot_content import GUIDES, POIS, SOURCES
from tourismo.main import app
from tourismo.core.database import get_db


def load_migration():
    filename = Path(__file__).parents[1] / 'migrations' / 'versions' / '0007_pilot_destination_guides.py'
    spec = importlib.util.spec_from_file_location('tourismo_pilot_migration', filename)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_pilot_catalog_has_five_distinct_sourced_english_guides():
    assert set(GUIDES) == {'kandy', 'galle', 'anuradhapura', 'sigiriya', 'nuwara-eliya'}
    assert len(POIS) >= 10
    assert len({(slug, poi_slug) for slug, poi_slug, *_ in POIS}) == len(POIS)
    assert all(name and url.startswith('https://') for name, url in SOURCES.values())
    for slug, guide in GUIDES.items():
        assert guide['source'] in SOURCES, slug
        assert len(guide['overview']) > 200
        assert guide['original_overview']
        assert len(guide['highlights']) >= 3
        assert len(guide['local_tips']) >= 3
        assert len(set(guide['highlights'])) == len(guide['highlights'])
    for slug, poi_slug, title, category, source_key, description, local_tip in POIS:
        assert slug in GUIDES
        assert source_key in SOURCES
        assert category in {'heritage', 'nature', 'landmark', 'beach', 'wildlife', 'culture', 'adventure'}
        assert poi_slug and title and len(description) > 45 and local_tip


def test_migration_is_nondestructive_and_editor_safe(monkeypatch):
    mod = load_migration()
    assert mod.down_revision == '0006_editorial_quality'
    statements = []
    monkeypatch.setattr(mod.op, 'execute', lambda stmt: statements.append(stmt))
    mod.upgrade()
    assert len(statements) == len(SOURCES) + len(GUIDES) + 2 * len(POIS)
    sql = '\n'.join(str(s) for s in statements).lower()
    assert "g.content_status='sample'" in sql
    assert 'g.overview=:original_overview' in sql
    assert 'not exists' in sql and 'destination_guide_revisions' in sql
    assert "when d.content_status='published' then 'draft'" in sql
    assert "p.content_status in ('sample', 'draft')" in sql
    assert 'on conflict' in sql
    assert 'cast(:id as uuid)' in sql and 'cast(:source_id as uuid)' in sql
    assert 'delete from' not in sql and 'update users' not in sql
    assert 'set content_status=\'published\'' not in sql
    assert 'insert into destination_photos' not in sql


def test_existing_public_apis_remain_guest_accessible():
    app.dependency_overrides[get_db] = lambda: object()
    try:
        with TestClient(app) as client:
            assert client.get('/api/v1/health/live').status_code == 200
            assert client.get('/api/v1/admin/content-audit').status_code == 401
            assert client.get('/api/v1/destinations/kandy/guide?locale=invalid').status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_stable_seed_identifiers():
    mod = load_migration()
    assert mod.stable_id('source', 'kandy_heritage') == mod.stable_id('source', 'kandy_heritage')
    assert mod.stable_id('poi', 'kandy:temple-of-the-tooth-relic') != mod.stable_id('poi', 'galle:galle-fort-ramparts')
