"""Phase 5.4: bounded viewport, category fairness and editorial source QA."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.dialects.postgresql import dialect
from sqlalchemy.orm import Session

from tourismo.main import app
from tourismo.core.database import get_db
from tourismo.maps.routes import MapPoint, _balanced_viewport, public_map_viewport
from tourismo.maps.geo_quality import assess_geographic_quality


def point(index, kind='destination'):
    return MapPoint(id=f'{kind}:{uuid.UUID(int=index+1)}', kind=kind,
                    title=f'Example {index}', latitude=7.1+(index%30)*.001,
                    longitude=80.6, category='heritage', district='Kandy',
                    detail_path='/destinations/example', location_note='Synthetic test pin')


def test_balanced_viewport_caps_120_synthetic_points_and_interleaves_categories():
    # Test-only fixtures, never added to the product or presented as real hotels.
    records=[point(i,'destination') for i in range(120)] + [point(i+120,'attraction') for i in range(25)]
    records += [point(i+150,'service') for i in range(50)]
    result=_balanced_viewport(records, limit=120)
    assert len(result.points)==120 and result.has_more is True
    assert [p.kind for p in result.points[:6]] == ['destination','attraction','service']*2
    assert len({p.id for p in result.points})==120
    assert set(p.kind for p in result.points)=={'destination','attraction','service'}


def test_viewport_not_truncated_at_or_under_limit():
    result=_balanced_viewport([point(0),point(1)],limit=20)
    assert result.has_more is False
    assert len(result.points)==2


def test_viewport_rejects_huge_or_invalid_queries_before_database_access():
    app.dependency_overrides[get_db]=lambda: Mock()
    try:
        with TestClient(app) as client:
            for qs in ('?limit=251','?limit=1','?north=4&south=9',
                       '?south=-90&north=90','?kind=vendor','?west=bad',
                       '?north=NaN'):
                res=client.get('/api/v1/map/viewport'+qs)
                assert res.status_code==422,(qs,res.text)
    finally:
        app.dependency_overrides.pop(get_db,None)


def test_viewport_retains_public_visibility_and_has_more(monkeypatch):
    import tourismo.maps.routes as routes
    called=[]
    def synthetic(db,south,west,north,east,kind,cap_per_kind=None):
        called.append((south,west,north,east,kind,cap_per_kind))
        return [point(i,'service') for i in range(65)]
    monkeypatch.setattr(routes,'_map_points',synthetic)
    app.dependency_overrides[get_db]=lambda: Mock()
    try:
        with TestClient(app) as client:
            r=client.get('/api/v1/map/viewport?limit=20&kind=service')
            assert r.status_code==200,r.text
            body=r.json()
            assert len(body['points'])==20
            assert body['has_more'] is True and body['limit']==20
            assert called[0][-2:]==('service',21)
            assert all('public_email' not in v and 'vendor_evidence' not in v for v in body['points'])
    finally:
        app.dependency_overrides.pop(get_db,None)


def test_quality_report_flags_missing_sources_bounds_duplicates_but_does_not_move_points():
    records=[('destination','Kandy','/destinations/kandy','Kandy',None,None,None),
             ('attraction','Museum','/destinations/kandy','Kandy',7.29,80.63,'https://example.org/pin'),
             ('service','Cafe','/listings/cafe','Kandy',7.29,80.63,None),
             ('service','Remote','/listings/remote','Badulla',12,80,'https://example.org/pin')]
    output=assess_geographic_quality(records,max_issues=12)
    assert (output.scanned,output.mapped,output.sourced_mapped)==(4,3,2)
    assert output.missing_coordinates==1
    assert output.missing_location_source==1
    assert output.outside_review_bounds==1
    assert output.shared_coordinate_groups==1
    assert len([v for v in output.issues if v.reason=='shared_coordinates_review'])==2
    assert records[1][4:6]==(7.29,80.63)  # read-only audit


def test_quality_report_truncation_is_explicit():
    data=[('destination',f'Example {i}',f'/destinations/{i}','Kandy',None,None,None) for i in range(120)]
    result=assess_geographic_quality(data,max_issues=4,scan_limited=True)
    assert len(result.issues)==4
    assert result.issues_limited and result.scan_limited


def test_quality_endpoint_requires_editor_auth_not_guest():
    app.dependency_overrides[get_db]=lambda: Mock()
    try:
        with TestClient(app) as client:
            assert client.get('/api/v1/admin/geo-quality').status_code==401
    finally:
        app.dependency_overrides.pop(get_db,None)


def test_public_map_source_unchanged_and_phase54_required_no_schema_change():
    from tourismo.listings.routes import _public_query
    sql=str(_public_query().compile(dialect=dialect(), compile_kwargs={'literal_binds':True}))
    assert "published" in sql and 'expired_license' in sql and 'vendor_evidence' in sql
    routes=(Path(__file__).parents[1]/'tourismo/maps/routes.py').read_text()
    assert 'cap_per_kind=limit + 1' in routes
    assert 'noload(ServiceListing.photos)' in routes
    assert 'from tourismo.demo' not in routes
    # Phase 5.4 itself added no migration. Later phases are allowed to add new revisions.
    migration_dir = Path(__file__).parents[1]/'migrations/versions'
    assert (migration_dir/'0015_location_links.py').exists()
