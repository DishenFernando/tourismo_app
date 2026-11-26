"""Phase 5.1: public map data security, bounds, sources, and no invented points."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import uuid

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.dialects.postgresql import dialect
from tourismo.maps.routes import safe_point, valid_bbox, _map_points, Geometry
from tourismo.core.models import Destination
from tourismo.listings.routes import _public_query
from tourismo.main import app
from tourismo.core.database import get_db
from sqlalchemy import cast, func


def test_invalid_coords_do_not_become_fake_map_pins():
    assert not safe_point(None, 80.65)
    assert not safe_point(float('nan'), 80.65)
    assert not safe_point(7.2, float('inf'))
    assert not safe_point('invalid', 80.65)
    assert safe_point(7.2, 80.65)


def test_bbox_is_bounded_and_rejects_odd_shapes():
    valid_bbox(5.5, 79.4, 10.1, 82.1)
    for bbox in [(10, 79, 5, 82), (5, 82, 10, 79), (-20, 79, 30, 82)]:
        with pytest.raises(HTTPException) as exc:
            valid_bbox(*bbox)
        assert exc.value.status_code == 422


def test_map_query_compiles_postgis_geometry_cast():
    text = str(func.ST_Y(cast(Destination.location, Geometry())).compile(dialect=dialect()))
    assert 'ST_Y' in text and 'CAST' in text and 'geometry' in text


def test_service_map_uses_existing_public_visibility_gate():
    query = str(_public_query().compile(dialect=dialect(), compile_kwargs={'literal_binds':True}))
    assert 'published' in query
    assert 'rejected' in query
    assert 'expired_license' in query
    assert 'vendor_evidence' in query


def test_public_map_rejects_bad_queries_before_database_use():
    app.dependency_overrides[get_db] = lambda: Mock()
    try:
        with TestClient(app) as client:
            for qs in ('?south=10&north=5', '?west=83&east=79',
                       '?kind=unknown', '?south=NaN', '?south=-80&north=60'):
                assert client.get('/api/v1/map/points'+qs).status_code == 422
    finally:
        app.dependency_overrides.pop(get_db,None)


def test_service_mapping_never_invents_badges_and_no_private_data():
    mock_db=Mock()
    approved=SimpleNamespace(verification_state='approved')
    unverified=SimpleNamespace(verification_state='draft')
    def listing(name,org,lat=7.3):
        return SimpleNamespace(id=uuid.uuid4(),title=name,slug=name.lower(),
            latitude=lat,longitude=80.6,category='accommodation',district='Kandy',
            organization=org,location_note='',location_source_url='https://example.org/coords')
    mock_db.scalars.return_value.all.return_value=[listing('Verified',approved), listing('Regular',unverified), listing('Missing',unverified,None)]
    result=_map_points(mock_db,5.5,79.4,10.1,82.1,'service')
    assert len(result)==2
    assert result[0].business_verified is True
    assert result[1].business_verified is False
    assert result[1].detail_path=='/listings/regular'
    assert 'business_name' not in result[0].model_dump()
    assert 'contact_email' not in result[0].model_dump()


def test_no_fictional_demo_query_in_public_map_module():
    text=(Path(__file__).parents[1]/'tourismo/maps/routes.py').read_text()
    assert "from tourismo.demo" not in text
    assert "_public_query()" in text
    assert "PointOfInterest.content_status.in_(['sample', 'published'])" in text


def test_config_uses_dev_tiles_but_production_requires_explicit_provider(monkeypatch):
    import tourismo.maps.routes as maps
    monkeypatch.setattr(maps, 'get_settings', lambda: SimpleNamespace(map_tile_url='',
        map_tile_attribution='OSM',app_environment='production',enable_demo_catalog=False))
    assert maps.public_map_config()['tile_url'] is None
    monkeypatch.setattr(maps, 'get_settings', lambda: SimpleNamespace(map_tile_url='',
        map_tile_attribution='OSM',app_environment='development',enable_demo_catalog=True))
    assert 'tile.openstreetmap.org' in maps.public_map_config()['tile_url']
    assert maps.public_map_config()['demo_mode'] is True
