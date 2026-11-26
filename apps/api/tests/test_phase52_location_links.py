"""Map-link import: accurate pins, safe redirects and editorial provenance."""
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from tourismo.admin.routes import CreatePlace, DestinationLocationEdit, PoiCreate
from tourismo.identity.security import require_user
from tourismo.main import app
from tourismo.maps.location_links import checked_url, extract_coordinates, resolve_location_link


@pytest.mark.parametrize('url,latitude,longitude,precision', [
    ('https://www.google.com/maps/place/Galle/data=!3d6.0329!4d80.2168', 6.0329,80.2168,'pin'),
    ('https://www.google.com/maps/search/?api=1&query=7.2906%2C80.6337',7.2906,80.6337,'pin'),
    ('https://www.google.com/maps/place/Galle/@6.033,80.217,17z',6.033,80.217,'map_center'),
    ('https://www.openstreetmap.org/?mlat=6.9271&mlon=79.8612#map=17/6.9/79.8',6.9271,79.8612,'pin'),
    ('https://www.openstreetmap.org/#map=16/6.9271/79.8612',6.9271,79.8612,'map_center'),
    ('https://maps.apple.com/?ll=6.9271,79.8612',6.9271,79.8612,'map_center'),
    ('https://www.bing.com/maps?cp=6.9271~79.8612',6.9271,79.8612,'map_center'),
])
def test_supported_map_formats(url, latitude, longitude, precision):
    point=resolve_location_link(url)
    assert (point.latitude,point.longitude,point.precision)==(latitude,longitude,precision)


@pytest.mark.parametrize('url', [
    'http://www.google.com/maps/place/Colombo/@6.9,79.8,17z',
    'https://evil.example/maps/place/Colombo/@6.9,79.8,17z',
    'https://google.com.evil.example/maps/@6.9,79.8,14z',
    'https://127.0.0.1/private?ll=6.9,79.8',
    'https://localhost/private?ll=6.9,79.8',
    'https://www.google.com:8443/maps/place/x/@6.9,79.8,14z',
    'https://attacker@www.google.com/maps/@6.9,79.8,14z',
    'https://goo.gl/anything?ll=6.9,79.8',
    'https://www.google.com/accounts?ll=6.9,79.8',
])
def test_untrusted_urls_rejected_before_network(url):
    with pytest.raises(HTTPException) as error:
        resolve_location_link(url)
    assert error.value.status_code==422


def test_short_link_only_follows_allowlisted_redirect():
    class FakeClient:
        def __init__(self,**kwargs):
            assert kwargs['follow_redirects'] is False
            assert kwargs['trust_env'] is False
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def head(self,url):
            assert url=='https://maps.app.goo.gl/allowed'
            return SimpleNamespace(status_code=302,headers={
                'location':'https://www.google.com/maps/place/Galle/data=!3d6.0329!4d80.2168'})
    with patch('tourismo.maps.location_links.httpx.Client',FakeClient):
        result=resolve_location_link('https://maps.app.goo.gl/allowed')
    assert result.latitude==6.0329
    assert result.source_url=='https://maps.app.goo.gl/allowed'


def test_short_link_blocks_host_redirect_before_following_it():
    class EvilClient:
        def __init__(self,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def head(self,url):
            assert url=='https://maps.app.goo.gl/allowed'
            return SimpleNamespace(status_code=302,headers={'location':'https://169.254.169.254/latest/meta-data'})
    with patch('tourismo.maps.location_links.httpx.Client',EvilClient):
        with pytest.raises(HTTPException) as error:
            resolve_location_link('https://maps.app.goo.gl/allowed')
    assert error.value.status_code==422


def test_named_place_does_not_invent_coordinates():
    with pytest.raises(HTTPException) as error:
        resolve_location_link('https://www.google.com/maps/search/?api=1&query=Galle+Fort')
    assert 'does not expose coordinates' in error.value.detail


def test_outside_sri_lanka_is_rejected():
    with pytest.raises(HTTPException) as error:
        resolve_location_link('https://www.google.com/maps/search/?api=1&query=48.8584%2C2.2945')
    assert 'outside Sri Lanka' in error.value.detail


def test_destination_location_provenance_and_pair_are_required():
    details=dict(slug='test-place',title='Test place',district='Galle',province='Southern')
    assert CreatePlace(**details,latitude=6.05,longitude=80.2,
        location_source_url='https://www.openstreetmap.org/?mlat=6.05&mlon=80.2').latitude==6.05
    with pytest.raises(ValidationError):
        CreatePlace(**details,latitude=6.05,longitude=80.2)
    with pytest.raises(ValidationError):
        DestinationLocationEdit(latitude=6.05,longitude=None,
                                location_source_url='https://www.openstreetmap.org')
    assert DestinationLocationEdit(latitude=None,longitude=None,location_source_url=None).latitude is None


def test_attraction_preserves_existing_editorial_source_contract():
    base=dict(slug='test-poi',title='Test attraction',description='Historic place',category='heritage',
              source_url='https://whc.unesco.org/en/list/450/',source_name='UNESCO')
    assert PoiCreate(**base,latitude=6.05,longitude=80.2).latitude==6.05
    assert PoiCreate(**base,latitude=6.05,longitude=80.2,
                     location_source_url='https://www.openstreetmap.org/?mlat=6.05&mlon=80.2').latitude==6.05


def test_resolver_endpoint_requires_signin():
    with TestClient(app) as client:
        response=client.post('/api/v1/map/resolve-location',json={
            'url':'https://www.openstreetmap.org/?mlat=6.9271&mlon=79.8612'})
    assert response.status_code==401


def test_authenticated_resolve_does_not_write_to_database():
    app.dependency_overrides[require_user]=lambda: SimpleNamespace(id='test-user')
    try:
        with TestClient(app) as client:
            response=client.post('/api/v1/map/resolve-location',json={
                'url':'https://www.openstreetmap.org/?mlat=6.9271&mlon=79.8612'})
        assert response.status_code==200,response.text
        assert response.json()['latitude']==6.9271
    finally:
        app.dependency_overrides.clear()


def test_public_destination_location_requires_administrator(monkeypatch):
    from tourismo.admin import routes as admin
    place=SimpleNamespace(id='place-id',slug='galle',content_status='published',location_source_url=None,location=None)
    db=SimpleNamespace(scalar=lambda query:place)
    monkeypatch.setattr(admin,'active_roles',lambda db,user:['editor'])
    with pytest.raises(HTTPException) as error:
        admin.update_destination_location('galle',DestinationLocationEdit(
            latitude=6.05,longitude=80.2,location_source_url='https://www.openstreetmap.org/?mlat=6.05&mlon=80.2'),
            db, SimpleNamespace(id='editor-id'))
    assert error.value.status_code==403
    assert place.location is None


def test_draft_destination_location_save_is_audited(monkeypatch):
    from tourismo.admin import routes as admin
    place=SimpleNamespace(id='place-id',slug='galle',content_status='draft',location_source_url=None,location=None)
    events=[]
    db=SimpleNamespace(scalar=lambda query:place,add=lambda event:events.append(event),commit=lambda:None)
    body=DestinationLocationEdit(latitude=6.05,longitude=80.2,
        location_source_url='https://www.openstreetmap.org/?mlat=6.05&mlon=80.2')
    result=admin.update_destination_location('galle',body,db,SimpleNamespace(id='editor-id'))
    assert result['status']=='saved'
    assert place.location_source_url==body.location_source_url
    assert len(events)==1 and events[0].action=='destination.location_changed'


def test_public_attraction_location_requires_administrator(monkeypatch):
    from tourismo.admin import routes as admin
    place=SimpleNamespace(id='place-id',slug='galle')
    poi=SimpleNamespace(id='poi-id',content_status='published',latitude=6.0,longitude=80.0)
    records=iter([place,poi]);db=SimpleNamespace(scalar=lambda query:next(records))
    monkeypatch.setattr(admin,'active_roles',lambda db,user:['editor'])
    with pytest.raises(HTTPException) as error:
        admin.update_poi_location('galle','test-poi',DestinationLocationEdit(
            latitude=6.05,longitude=80.2,location_source_url='https://www.openstreetmap.org/?mlat=6.05&mlon=80.2'),
            db,SimpleNamespace(id='editor-id'))
    assert error.value.status_code==403
    assert poi.latitude==6.0
