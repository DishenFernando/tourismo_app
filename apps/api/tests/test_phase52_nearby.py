"""Phase 5.2: nearby query safety, distance semantics and trust boundaries."""
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.dialects.postgresql import dialect

from tourismo.core.database import get_db
from tourismo.main import app
from tourismo.maps.routes import (
    NearbyCenter, _nearby_center, _nearby_points, _geography_point,
)


def center():
    return NearbyCenter(title='Kandy', latitude=7.291, longitude=80.634,
                        kind='selected_location')


def test_nearby_public_route_requires_one_valid_center():
    app.dependency_overrides[get_db] = lambda: Mock()
    try:
        with TestClient(app) as client:
            for query in (
                '', '?near_lat=7.2', '?near_lon=80.6',
                '?near_lat=NaN&near_lon=80',
                '?near_lat=7.2&near_lon=80&destination=kandy',
                '?near_lat=100&near_lon=80',
                '?near_lat=7&near_lon=80&radius_km=101',
                '?near_lat=7&near_lon=80&radius_km=-1',
                '?near_lat=7&near_lon=80&limit=61',
                '?near_lat=7&near_lon=80&kind=hotel',
                '?near_lat=7&near_lon=80&category=x%3Bdrop',
                '?near_lat=7&near_lon=80&q=' + 'x'*81,
            ):
                response = client.get('/api/v1/map/nearby' + query)
                assert response.status_code == 422, (query, response.text)
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_nearby_without_auth_is_public_and_returns_no_guessed_points():
    db = Mock()
    db.execute.return_value.all.return_value = []
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            response = client.get('/api/v1/map/nearby?near_lat=7.291&near_lon=80.634&radius_km=10')
            assert response.status_code == 200, response.text
            data = response.json()
            assert data['points'] == []
            assert data['center']['kind'] == 'selected_location'
            assert data['radius_km'] == 10
            assert 'straight-line' in data['distance_note']
            assert 'travel times' in data['distance_note']
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_public_destination_must_exist_and_have_coordinates():
    db = Mock()
    db.execute.return_value.first.return_value = None
    with pytest.raises(HTTPException) as exc:
        _nearby_center(db, 'missing', None, None)
    assert exc.value.status_code == 404
    place = SimpleNamespace(slug='kandy')
    db.execute.return_value.first.return_value = (place, 'Kandy', None, None)
    with pytest.raises(HTTPException) as exc:
        _nearby_center(db, 'kandy', None, None)
    assert exc.value.status_code == 422
    db.execute.return_value.first.return_value = (place, 'Kandy', 7.3, 80.6)
    result = _nearby_center(db, 'kandy', None, None)
    assert result.destination_slug == 'kandy'
    assert result.kind == 'destination'


def test_geography_uses_longitude_before_latitude_and_meters():
    sql = str(_geography_point(7.3, 80.6).compile(dialect=dialect(),
        compile_kwargs={'literal_binds': True}))
    assert 'ST_MakePoint(80.6, 7.3)' in sql
    assert 'geography' in sql


def test_all_nearby_types_use_postgis_radius_and_existing_visibility_gate():
    captured = []
    db = Mock()
    def execute(query):
        captured.append(str(query.compile(dialect=dialect(), compile_kwargs={'literal_binds': True})))
        return SimpleNamespace(all=lambda: [])
    db.execute.side_effect = execute
    response = _nearby_points(db, center(), 25, 'all', None, '', 60)
    assert response.points == []
    assert len(captured) == 3
    for sql in captured:
        assert 'ST_DWithin' in sql and 'ST_Distance' in sql
        assert '25000' in sql
        assert 'LIMIT' in sql
    service_sql = captured[-1]
    assert 'service_listings' in service_sql
    assert 'published' in service_sql
    assert 'rejected' in service_sql
    assert 'expired_license' in service_sql
    assert 'vendor_evidence' in service_sql


def test_nearby_category_and_text_filters_are_applied_to_database():
    captured = []
    db = Mock()
    def execute(stmt):
        captured.append(str(stmt.compile(dialect=dialect(), compile_kwargs={'literal_binds': True})))
        return SimpleNamespace(all=lambda: [])
    db.execute.side_effect = execute
    _nearby_points(db, center(), 5, 'service', 'restaurant', 'Kandy', 20)
    assert len(captured) == 1
    assert "'restaurant'" in captured[0]
    assert '%Kandy%' in captured[0]
    assert '5000' in captured[0]


def test_business_badge_only_for_verified_public_listings_and_order_by_distance():
    db = Mock()
    def listing(name, verified):
        return SimpleNamespace(id=uuid4(), title=name, latitude=7.3, longitude=80.6,
            slug=name.lower(), category='accommodation', district='Kandy',
            organization=SimpleNamespace(verification_state='approved' if verified else 'draft'),
            location_note='', location_source_url='https://example.com/map')
    verified = listing('Verified', True)
    regular = listing('Regular', False)
    db.execute.return_value.all.return_value = [(verified, 1500), (regular, 300)]
    result = _nearby_points(db, center(), 10, 'service', None, '', 1)
    assert len(result.points) == 1
    assert result.points[0].title == 'Regular'
    assert result.points[0].business_verified is False
    assert result.points[0].distance_km == 0.3
    assert result.has_more is True
    db.execute.return_value.all.return_value = [(verified, 1500)]
    result = _nearby_points(db, center(), 10, 'service', None, '', 60)
    assert result.points[0].business_verified is True
    assert 'email' not in result.points[0].model_dump()


def test_nearby_result_can_be_empty_without_inventing_locations():
    db = Mock()
    db.execute.return_value.all.return_value = []
    result = _nearby_points(db, center(), 5, 'all', None, '', 60)
    assert result.points == []
    assert result.has_more is False


def test_no_demo_catalog_import_or_private_data_endpoint():
    from pathlib import Path
    code = (Path(__file__).parents[1] / 'tourismo/maps/routes.py').read_text()
    assert 'from tourismo.demo' not in code
    assert 'stmt = (_public_query()' in code
    assert "Destination.content_status.in_(['sample', 'published'])" in code
    assert 'PointOfInterest.content_status.in_([' in code
