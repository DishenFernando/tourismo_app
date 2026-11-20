"""Phase 4.3: optional regional/family/geodesic discovery without publication bypass."""
import importlib.util
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import dialect

from tourismo.core.models import Destination, DestinationTranslation
from tourismo.listings import routes as listings
from tourismo.main import app
from tourismo.core.database import get_db


def sql_string(expression):
    return str(select(1).where(expression).compile(dialect=dialect()))


def test_family_filter_is_checked_by_database_before_limit_and_offset():
    query = sql_string(listings._eligible_room_predicate(2, [5, 12]))
    assert 'jsonb_array_elements' in query
    for key in ('max_adults', 'max_children', 'min_child_age', 'max_child_age', 'max_total_guests'):
        assert key in str(listings._eligible_room_predicate(2, [5, 12]).compile(
            dialect=dialect(), compile_kwargs={'literal_binds': True}))
    assert 'EXISTS' in query


def test_destination_search_does_not_claim_proximity():
    dest = Destination(slug='sigiriya', district='Matale', province='Central', content_status='sample')
    dest.translations = [DestinationTranslation(title='Sigiriya', locale='en', summary='')]
    statement = sql_string(listings._destination_area_predicate(dest))
    assert 'service_listings.district' in statement
    assert 'jsonb_array_elements_text' in statement
    assert 'service_areas' in str(listings._destination_area_predicate(dest).compile(
        dialect=dialect(), compile_kwargs={'literal_binds': True}))
    assert 'ST_Distance' not in statement


def test_geo_query_uses_postgis_geography_not_degree_based_distance():
    distance = str(listings._distance_meters(7.29, 80.64).compile(dialect=dialect()))
    assert 'ST_Distance' in distance and 'ST_MakePoint' in distance
    assert 'geography' in distance
    assert 'service_listings.latitude' in distance
    assert 'service_listings.longitude' in distance


def test_filter_validation_blocks_incomplete_or_misleading_requests():
    bad_cases = [
        {'category': 'restaurant', 'adults': 2},
        {'category': 'accommodation', 'child_ages': [3]},
        {'category': 'accommodation', 'adults': 1, 'child_ages': [19]},
        {'near_lat': 7.0},
        {'near_lon': 80.0},
        {'radius_km': 25.0},
        {'sort': 'distance'},
    ]
    # The endpoint can be called directly for validation, without a database.
    # FastAPI defaults are replaced by real inputs for all optional Query fields.
    args = dict(category=None, province=None, district=None, destination=None, q='',
                adults=None, child_ages=[], near_lat=None, near_lon=None,
                radius_km=None, sort='recent', limit=24, offset=0)
    for case in bad_cases:
        with pytest.raises(HTTPException) as exc:
            listings.public_listings(db=Mock(), **{**args, **case})
        assert exc.value.status_code == 422


def test_public_anonymous_endpoint_returns_validation_for_partial_geo():
    app.dependency_overrides[get_db] = lambda: Mock()
    try:
        with TestClient(app) as client:
            assert client.get('/api/v1/listings?near_lat=7.2').status_code == 422
            assert client.get('/api/v1/listings?category=restaurant&adults=2').status_code == 422
            assert client.get('/api/v1/listings?near_lat=NaN&near_lon=80.0').status_code == 422
            assert client.get('/api/v1/listings?near_lat=7&near_lon=80&radius_km=101').status_code == 422
            assert client.get('/api/v1/listings?child_ages=18&category=accommodation&adults=2').status_code == 422
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_discovery_keeps_original_verified_provider_gate():
    statement = str(listings._public_query().compile(dialect=dialect()))
    assert 'verification_state' in statement and 'expires_on' in statement
    assert 'published' in str(listings._public_query().compile(dialect=dialect(),
                             compile_kwargs={'literal_binds': True}))


def test_additive_index_migration_version_and_contents():
    path = Path(__file__).parents[1] / 'migrations' / 'versions' / '0012_listing_discovery_indexes.py'
    spec = importlib.util.spec_from_file_location('tourismo_phase43_migration', path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    assert module.down_revision == '0011_advanced_listings'
    assert module.revision == '0012_listing_discovery_indexes'
    class Ops:
        def __init__(self): self.statements=[]; self.indexes=[]
        def create_index(self, *args, **kwargs): self.indexes.append((args, kwargs))
        def execute(self, statement): self.statements.append(str(statement))
    ops=Ops()
    original=module.op
    module.op=ops
    try: module.upgrade()
    finally: module.op=original
    assert any('GIST' in text and 'ST_MakePoint' in text for text in ops.statements)
    assert any('status' in str(kwargs.get('postgresql_where')) for _,kwargs in ops.indexes)


def test_demo_catalog_remains_private_draft_only_and_can_test_regional_filters():
    from tourismo.demo import routes as demo
    assert 'tourismo-demo-' in str(demo._demo_query().compile(
        dialect=dialect(), compile_kwargs={'literal_binds': True}))
    assert 'draft' in str(demo._demo_query().compile(
        dialect=dialect(), compile_kwargs={'literal_binds': True}))
    with pytest.raises(HTTPException) as exc:
        demo.demo_listings(category='restaurant', adults=2, child_ages=[],
                           district=None, province=None, destination=None, q='', limit=24, db=Mock())
    assert exc.value.status_code == 422
