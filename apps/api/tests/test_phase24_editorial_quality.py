"""Phase 2.4 regression: safe publication, authorization, catalog completeness.

These tests do not require PostgreSQL; the migration is exercised by CI with PostGIS.
"""
import importlib.util
from pathlib import Path
import uuid

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from tourismo.admin import routes as admin
from tourismo.core.database import get_db
from tourismo.core.models import (
    Base, Destination, DestinationGuide, DestinationTranslation,
    GuideRevision, ContentSource, User,
)
from tourismo.main import app


class Result:
    def __init__(self, rows):
        self.rows = rows
    def all(self):
        return self.rows


class StubDb:
    def __init__(self, place, guide):
        self.place, self.guide = place, guide
        self.revision = None
        self.sources = []
        self.commits = 0
        self.events = []

    def scalar(self, query):
        # Source state is controlled by the fake, not the query text.
        entity = query.column_descriptions[0].get('entity')
        if entity is Destination:
            return self.place
        if entity is DestinationGuide:
            return self.guide
        if entity is GuideRevision:
            return self.revision
        return None

    def add(self, obj):
        self.events.append(obj)
        if isinstance(obj, GuideRevision):
            self.revision = obj
        if isinstance(obj, ContentSource):
            obj.id = uuid.uuid4()
            self.sources.append(obj)

    def flush(self):
        return None

    def commit(self):
        self.commits += 1


def user():
    return User(id=uuid.uuid4(), auth_subject='user_editor', status='active')


def fixtures():
    place_id = uuid.uuid4()
    place = Destination(id=place_id, slug='galle', content_status='published',
                        district='Galle', province='Southern')
    place.translations = [DestinationTranslation(locale='en', title='Galle', summary='')]
    guide = DestinationGuide(id=uuid.uuid4(), destination_id=place_id, locale='en',
                             overview='The approved historic description of Galle Fort is still public.',
                             highlights=['Approved content'], local_tips=[],
                             content_status='published', source_id=uuid.uuid4())
    return place, guide


def test_published_guide_remains_unchanged_when_editor_saves_revision():
    place, guide = fixtures()
    db = StubDb(place, guide)
    original = guide.overview
    data = admin.GuideEdit(locale='en', overview='An updated researched guide to the Galle Fort history and architecture.',
                           highlights=['UNESCO heritage'], local_tips=['Check current notices'],
                           source_name='UNESCO', source_url='https://whc.unesco.org/en/list/451/')
    result = admin.save_guide('galle', data, db, user())
    assert result['status'] == 'draft'
    assert guide.overview == original
    assert guide.content_status == 'published'
    assert db.revision is not None
    assert db.revision.status == 'draft'
    assert db.revision.source_id

    sent = admin.submit_guide('galle', 'en', db, user())
    assert sent['content_status'] == 'submitted'
    assert guide.overview == original
    assert db.revision.status == 'submitted'

    with pytest.raises(HTTPException) as exc:
        admin.save_guide('galle', data, db, user())
    assert exc.value.status_code == 409

    reviewed = admin.approve_guide('galle', 'en', db, user())
    assert reviewed['content_status'] == 'published'
    assert guide.overview == data.overview
    assert guide.highlights == ['UNESCO heritage']
    assert db.revision.status == 'approved'
    assert db.revision.reviewed_by is not None


def test_admin_returns_revision_without_hiding_approved_guide():
    place, guide = fixtures()
    db = StubDb(place, guide)
    revision = GuideRevision(guide_id=guide.id, version=1,
                             overview='Revised editorial content about Galle and its historic fortifications.',
                             highlights=[], local_tips=[], source_id=uuid.uuid4(), status='submitted')
    db.revision = revision
    previous = guide.overview
    admin.reject_guide('galle', admin.ReviewDecision(reason='Source details need verification'), 'en', db, user())
    assert revision.status == 'draft'
    assert guide.overview == previous
    assert guide.content_status == 'published'


def test_public_api_still_requires_no_auth_for_destinations():
    app.dependency_overrides[get_db] = lambda: object()
    try:
        with TestClient(app) as client:
            assert client.get('/api/v1/admin/content-audit').status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_content_audit_distinguishes_catalog_from_reviewed_content():
    place, guide = fixtures()
    place.photos = []
    class AuditDb:
        def __init__(self):
            self.calls = 0
        def scalars(self, _query):
            self.calls += 1
            return Result([[place], [guide], []][self.calls-1])
    quality = admin.content_audit(AuditDb(), user())
    assert quality['total'] == 1
    assert quality['published'] == 1
    assert quality['needs_attention'] == 1
    record = quality['destinations'][0]
    assert 'licensed_photo_missing' in record['missing']
    assert 'approved_attractions_missing' in record['missing']
    assert 'sinhala_translation_missing' in record['missing']
    assert 'tamil_translation_missing' in record['missing']


def test_migration_additive_and_schema_revision_defined(monkeypatch):
    path = Path(__file__).parents[1] / 'migrations' / 'versions' / '0006_editorial_quality.py'
    spec = importlib.util.spec_from_file_location('phase24_migration', path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.down_revision == '0005_rich_destination_review'
    created = []
    monkeypatch.setattr(module.op, 'create_table', lambda name, *_args: created.append(name))
    monkeypatch.setattr(module.op, 'create_index', lambda *_args: None)
    module.upgrade()
    assert created == ['destination_guide_revisions']
    assert 'users' in Base.metadata.tables and 'trips' in Base.metadata.tables
    assert 'destination_guide_revisions' in Base.metadata.tables
