"""Phase 2.3 content gallery, review security and geo source regression tests.

Full PostGIS integration is exercised separately by the project CI database job.
"""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import uuid

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql
from tourismo.admin import routes as admin
from tourismo.core.database import get_db
from tourismo.core.models import Base, User
from tourismo.geography import routes as geography
from tourismo.main import app


class ScalarResult:
    def __init__(self, rows):
        self.rows = rows
    def all(self):
        return self.rows


class DB:
    def __init__(self, place, guide=None, pois=None):
        self.place, self.guide, self.pois = place, guide, pois or []
        self.scalar_calls = 0
        self.commits = 0
        self.events = []
    def scalar(self, _query):
        self.scalar_calls += 1
        return self.place if self.scalar_calls % 2 else self.guide
    def scalars(self, _query):
        return ScalarResult(self.pois)
    def add(self, obj):
        self.events.append(obj)
    def commit(self):
        self.commits += 1


def _place():
    return SimpleNamespace(id=uuid.uuid4(), slug='galle', content_status='sample', photos=[
        SimpleNamespace(image_url='https://commons.wikimedia.org/wiki/Special:FilePath/One.jpg',
                        file_page_url='https://commons.wikimedia.org/wiki/File:One.jpg',
                        photographer='Creator', license_name='CC BY 4.0',
                        license_url='https://creativecommons.org/licenses/by/4.0/',
                        alt_text='Galle fort', is_primary=True)])


def _user():
    return User(id=uuid.uuid4(), auth_subject='user_editor', status='active')


def test_gallery_has_real_file_credit_and_url():
    photos = geography.destination_photos('galle', DB(_place()))
    assert len(photos) == 1
    assert photos[0].file_page_url.startswith('https://commons.wikimedia.org/wiki/File:')
    assert photos[0].photographer == 'Creator'
    assert photos[0].license_url.startswith('https://creativecommons.org/')


def test_invalid_poi_coordinates_are_rejected():
    data = dict(slug='example-site', title='Example site', description='Historic heritage destination',
                category='heritage', source_url='https://whc.unesco.org/en/list/450/', source_name='UNESCO')
    assert admin.PoiCreate(**data, latitude=7.2, longitude=80.6).latitude == 7.2
    for invalid in (dict(latitude=7.2), dict(latitude=150, longitude=80),
                    dict(latitude=7.2, longitude=200)):
        with pytest.raises(ValueError):
            admin.PoiCreate(**data, **invalid)
    with pytest.raises(ValueError):
        admin.PoiCreate(**{**data, 'source_url':None}, latitude=7.2, longitude=80)
    with pytest.raises(ValueError):
        admin.PoiCreate(**{**data, 'source_url':'http://insecure.test'}, latitude=7.2, longitude=80)


def test_guide_editor_must_attach_source_before_submitting():
    place = _place()
    guide = SimpleNamespace(content_status='draft', source_id=None,
                            overview='Some historic context in Galle' * 3)
    db = DB(place, guide)
    with pytest.raises(HTTPException) as exc:
        admin.submit_guide('galle', 'en', db, _user())
    assert exc.value.status_code == 422
    assert not db.commits
    guide.source_id = uuid.uuid4()
    result = admin.submit_guide('galle', 'en', db, _user())
    assert result['content_status'] == 'submitted'
    assert db.commits == 1


def test_admin_can_return_guide_with_reason():
    place = _place()
    guide = SimpleNamespace(content_status='submitted', source_id=uuid.uuid4(),
                            overview='A long heritage description explaining Galle and its fortifications')
    db = DB(place, guide)
    decision = admin.ReviewDecision(reason='Verify this description against the UNESCO record')
    result = admin.reject_guide('galle', decision, 'en', db, _user())
    assert result['content_status'] == 'draft'
    assert db.commits == 1
    assert any('Verify this description' in item.reason for item in db.events)
    with pytest.raises(HTTPException) as exc:
        admin.reject_guide('galle', decision, 'en', db, _user())
    assert exc.value.status_code == 409


def test_new_editorial_endpoints_reject_anonymous_requests():
    app.dependency_overrides[get_db] = lambda: object()
    try:
        with TestClient(app) as client:
            endpoints = [
                ('get','/api/v1/admin/review-queue'),
                ('post','/api/v1/admin/destinations/galle/guide/submit'),
                ('post','/api/v1/admin/destinations/galle/guide/approve'),
                ('post','/api/v1/admin/destinations/galle/guide/request-changes'),
                ('post','/api/v1/admin/destinations/galle/pois/fort/submit'),
                ('post','/api/v1/admin/destinations/galle/pois/fort/request-changes'),
            ]
            for method, path in endpoints:
                response = getattr(client, method)(path)
                assert response.status_code == 401, path
    finally:
        app.dependency_overrides.clear()


def test_migration_adds_coordinates_without_overwriting_curated_content(monkeypatch):
    path = Path(__file__).parents[1]/'migrations'/'versions'/'0005_rich_destination_review.py'
    spec = importlib.util.spec_from_file_location('phase23_migration',path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    statements = []
    monkeypatch.setattr(mod.op, 'execute', lambda stmt: statements.append(stmt))
    monkeypatch.setattr(mod.op, 'add_column', lambda *args,**kwargs:None)
    monkeypatch.setattr(mod.op, 'create_check_constraint',lambda *args,**kwargs:None)
    mod.upgrade()
    assert len(statements) == 4 + len(mod.UNESCO_SITES)
    sql = '\n'.join(str(statement.compile(dialect=postgresql.dialect())) for statement in statements)
    assert "location IS NULL" in sql
    assert 'ON CONFLICT' in sql
    assert 'ST_SetSRID' in sql and 'ST_MakePoint' in sql
    assert 'UPDATE users' not in sql and 'DELETE FROM trips' not in sql
    assert len({s[0] for s in mod.UNESCO_SITES}) == 4
    assert {'latitude', 'longitude'} <= set(Base.metadata.tables['poi'].columns.keys())
