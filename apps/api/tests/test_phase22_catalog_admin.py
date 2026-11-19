"""Phase 2.2 offline checks. DB integration still requires PostgreSQL/PostGIS."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import uuid

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql
from tourismo.admin.routes import CreatePlace, GuideEdit, PhotoCreate
from tourismo.admin.permissions import require_admin, require_editor, active_roles
from tourismo.core.models import User
from tourismo.geography.catalog_data import PLACES, COMMONS_PHOTOS
from tourismo.geography.routes import shape
from tourismo.main import app
from tourismo.core.database import get_db


def test_catalog_covers_all_nine_provinces_and_no_duplicate_place_slugs():
    assert len(PLACES) >= 100
    assert len({slug for slug, *_ in PLACES}) == len(PLACES)
    assert len({province for _, _, _, province in PLACES}) == 9
    assert all(len(row) == 4 and all(row) for row in PLACES)
    assert {'ella','galle','kandy','nuwara-eliya','anuradhapura'}.issubset({row[0] for row in PLACES})


def test_curated_photos_have_real_creators_and_cc_licenses():
    assert len(COMMONS_PHOTOS) >= 15
    slugs = {place[0] for place in PLACES}
    assert all(p[0] in slugs and p[2].strip() and p[3].startswith('CC BY') for p in COMMONS_PHOTOS)
    assert len({p[0] for p in COMMONS_PHOTOS}) == len(COMMONS_PHOTOS)


def test_photo_response_has_license_and_credit():
    image = SimpleNamespace(image_url='https://commons.wikimedia.org/wiki/Special:FilePath/Example.jpg',
            file_page_url='https://commons.wikimedia.org/wiki/File:Example.jpg',
            photographer='Photographer',license_name='CC BY-SA 4.0',
            license_url='https://creativecommons.org/licenses/by-sa/4.0/',
            alt_text='Beach in Sri Lanka',is_primary=True)
    translation = SimpleNamespace(locale='en',title='Example place',summary='Sample description')
    obj = SimpleNamespace(slug='example',district='Matara',province='Southern',
                          content_status='sample',translations=[translation],photos=[image])
    result=shape(obj)
    assert result.photo is not None
    assert result.photo.photographer == 'Photographer'
    assert result.photo.license_name == 'CC BY-SA 4.0'


def test_admin_and_editor_endpoints_never_allow_anonymous_access():
    app.dependency_overrides[get_db] = lambda: object()
    try:
        with TestClient(app) as client:
            assert client.get('/api/v1/admin/destinations').status_code == 401
            assert client.post('/api/v1/admin/destinations',json={}).status_code == 401
            assert client.post('/api/v1/admin/destinations/kandy/publish').status_code == 401
            assert client.post('/api/v1/admin/destinations/kandy/photos',json={}).status_code == 401
            assert client.get('/api/v1/admin/destinations/kandy/pois').status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_admin_schema_forbids_browser_supplied_role_and_status():
    with pytest.raises(ValueError):
        CreatePlace.model_validate({'slug':'a','title':'New place','district':'Galle',
            'province':'Southern','role':'admin','content_status':'published'})
    with pytest.raises(ValueError):
        GuideEdit.model_validate({'overview':'A'*80,'source_url':'http://insecure.example'})
    good = GuideEdit.model_validate({'overview':'A'*80,'source_url':'https://whc.unesco.org/en/list/451/'})
    assert good.locale == 'en'
    good_photo=PhotoCreate(filename='Nine_Arch_Bridge_Ella.jpg',photographer='Esh7788',
                           license_name='CC BY-SA 4.0',alt_text='Sri Lanka railway bridge')
    assert good_photo.filename.endswith('.jpg')
    with pytest.raises(ValueError):
        PhotoCreate(filename='../../etc/passwd',photographer='Bad',
                    license_name='CC BY-SA 4.0',alt_text='Not a photograph')


def test_no_self_assigned_admin_rights_without_db_role():
    user=User(id=uuid.uuid4(), auth_subject='user_example',status='active')
    class EmptyDb:
        def scalars(self,_statement):
            return self
        def all(self):
            return []
    db=EmptyDb()
    assert active_roles(db,user) == []
    with pytest.raises(HTTPException) as exception:
        require_editor(user=user,db=db)
    assert exception.value.status_code == 403
    with pytest.raises(HTTPException) as exception:
        require_admin(user=user,db=db)
    assert exception.value.status_code == 403


def test_migration_uses_uuid_cast_and_additive_conflict_safe_seed(monkeypatch):
    path=Path(__file__).parents[1]/'migrations'/'versions'/'0004_catalog_admin_media.py'
    spec=importlib.util.spec_from_file_location('phase22_catalog_migration',path)
    assert spec and spec.loader
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    statements=[]
    monkeypatch.setattr(mod.op,'execute',lambda sql:statements.append(sql))
    monkeypatch.setattr(mod.op,'create_table',lambda *a,**kw:None)
    monkeypatch.setattr(mod.op,'create_index',lambda *a,**kw:None)
    mod.upgrade()
    assert len(statements)==2+len(PLACES)*2+len(COMMONS_PHOTOS)
    sql='\n'.join(str(s.compile(dialect=postgresql.dialect())) for s in statements)
    assert sql.count('ON CONFLICT') >= len(PLACES)*2
    assert 'CAST(' in sql and 'AS UUID)' in sql
    assert "'sample'" in sql
    assert 'DELETE FROM users' not in sql and 'UPDATE trips' not in sql
