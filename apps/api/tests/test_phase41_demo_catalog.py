"""Synthetic preview never bypasses platform approval gates or authenticates fake users."""
from unittest.mock import Mock
from pathlib import Path
import uuid

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql

from tourismo.core.models import ServiceListing
from tourismo.core.config import Settings
from tourismo.demo import routes as demo
from tourismo.listings.routes import _public_query
from tourismo.main import app


def test_disabled_by_default_and_in_production_even_when_explicitly_enabled(monkeypatch):
    monkeypatch.setattr(demo, 'get_settings', lambda: Settings(_env_file=None, app_environment='development', enable_demo_catalog=False))
    assert demo.demo_enabled() is False
    with pytest.raises(HTTPException) as exc:
        demo.require_demo()
    assert exc.value.status_code == 404
    monkeypatch.setattr(demo, 'get_settings', lambda: Settings(_env_file=None, app_environment='production', enable_demo_catalog=True))
    assert demo.demo_enabled() is False
    with pytest.raises(HTTPException):
        demo.require_demo()
    monkeypatch.setattr(demo, 'get_settings', lambda: Settings(_env_file=None, app_environment='development', enable_demo_catalog=True))
    assert demo.demo_enabled() is True


def test_routes_return_404_when_disabled(monkeypatch):
    monkeypatch.setattr(demo, 'get_settings', lambda: Settings(_env_file=None, app_environment='production', enable_demo_catalog=True))
    with TestClient(app) as client:
        assert client.get('/api/v1/demo/status').json() == {'enabled':False}
        assert client.get('/api/v1/demo/listings').status_code == 404
        assert client.get('/api/v1/demo/listings/anything').status_code == 404


def test_demo_read_does_not_contain_contacts_or_private_fields():
    listing=ServiceListing(id=uuid.uuid4(),organization_id=uuid.uuid4(),slug='tourismo-demo-test',
        category='restaurant',title='[DEMO] Place',summary='Fake!',description='Only a fake preview',
        province='Central',district='Kandy',public_email='private@example.com',
        public_phone='+94111222333',details={'cuisines':['Sri Lankan']},status='draft')
    listing.photos=[]
    result=demo.demo_dict(listing)
    assert result['is_demo'] is True
    assert result['status'] == 'draft'
    assert result['public_email'] is None and result['public_phone'] is None
    assert result['booking_available'] is False
    assert all(field not in result for field in ('owner_id','organization_id','license_no','verification_state'))
    assert 'Fictional' in result['demo_disclaimer']


def test_fictional_query_does_not_change_approved_public_query():
    stmt=str(demo._demo_query().compile(dialect=postgresql.dialect()))
    public=str(_public_query().compile(dialect=postgresql.dialect()))
    assert 'service_listings.slug LIKE' in stmt
    assert 'vendor_organizations.business_name LIKE' in stmt
    assert 'service_listings.status' in stmt
    assert 'vendor_organizations.verification_state' in stmt
    assert 'NOT (EXISTS' in public
    assert 'vendor_organizations.verification_state' in public
    assert 'service_listings.status' in public


def test_seed_has_no_real_user_updates_no_admin_grants_no_approved_demo_records():
    # SQL file belongs to downloadable demo data pack, not version-controlled app patch.
    sql=Path('/mnt/data/Tourismo_Phase41_Fictional_Demo_Seed.sql')
    if not sql.exists():
        pytest.skip('Standalone data file not available in current test environment')
    text=sql.read_text()
    assert 'ON CONFLICT (id) DO NOTHING' in text
    assert "'draft'" in text
    assert "'published'" not in text
    assert "'approved'" not in text
    assert 'UPDATE public.users' not in text
    assert 'user_role_assignments' not in text
    assert text.count('INSERT INTO public.vendor_organizations') == 12
    assert text.count('INSERT INTO public.service_listings') == 24
    assert text.count('INSERT INTO public.users') == 4
