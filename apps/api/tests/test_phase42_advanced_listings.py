"""Phase 4.2: child-age conditions, source-backed map location and safe published revisions."""
import importlib.util
import uuid
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from tourismo.core.models import ServiceListing, ServiceListingRevision, User, VendorOrganization
from tourismo.listings import routes as listings
from tourismo.main import app

BASE = {
    'title': 'Garden family accommodation',
    'summary': 'Private accommodation beside the mountain railway station.',
    'description': 'A family guesthouse offering accommodation to visiting families. '
                   'Contact the provider to verify child policies and pricing.',
    'public_email': 'hello@example.org', 'public_phone': None,
    'details': {'room_types': [{'name': 'Family bedroom', 'max_adults': 2, 'max_children': 2,
               'number_of_rooms': 2, 'min_child_age': 4, 'max_child_age': 15,
               'max_total_guests': 4, 'indicative_nightly_lkr_minor': 1250000}]},
}


def test_room_age_rules_are_strict_and_backwards_compatible():
    room = listings.validate_details('accommodation', BASE['details'])['room_types'][0]
    assert room['min_child_age'] == 4 and room['max_child_age'] == 15
    legacy = {'room_types':[{'name':'Legacy family room', 'max_adults':2,
                             'max_children':1, 'number_of_rooms':1}]}
    assert listings.validate_details('accommodation', legacy)['room_types'][0]['min_child_age'] is None
    for key, value in [('min_child_age', 18), ('max_child_age', -1), ('max_total_guests', 7)]:
        invalid = {'room_types': [{**BASE['details']['room_types'][0], key: value}]}
        with pytest.raises(HTTPException) as exc:
            listings.validate_details('accommodation', invalid)
        assert exc.value.status_code == 422
    invalid_age = {'room_types': [{**BASE['details']['room_types'][0],
                                   'min_child_age': 12, 'max_child_age': 6}]}
    with pytest.raises(HTTPException):
        listings.validate_details('accommodation', invalid_age)


def test_family_fit_checks_each_child_age_without_booking_claims():
    details = listings.validate_details('accommodation', BASE['details'])
    assert listings.evaluate_family_fit(details, 2, [5, 12])['any_room_may_fit']
    assert not listings.evaluate_family_fit(details, 2, [3, 12])['any_room_may_fit']
    assert not listings.evaluate_family_fit(details, 3, [5])['any_room_may_fit']
    assert not listings.evaluate_family_fit(details, 2, [5, 8, 12])['any_room_may_fit']
    result = listings.evaluate_family_fit(details, 2, [5, 12])
    assert 'No availability' in result['disclaimer']
    assert result['rooms'][0]['age_policy_specified']


def test_map_reference_requires_pair_and_https_source():
    valid = listings.ListingWrite.model_validate({**BASE, 'latitude': 6.9271,
        'longitude': 79.8612, 'location_source_url': 'https://www.openstreetmap.org/#map=16/6.9271/79.8612'})
    assert valid.longitude == 79.8612
    for changes in [
        {'latitude': 6.92},
        {'longitude': 79.86},
        {'latitude': 6.92, 'longitude': 79.86},
        {'latitude': 6.92, 'longitude': 79.86, 'location_source_url':'http://example.org'},
        {'latitude': 6.92, 'longitude': 79.86, 'location_source_url':'https://localhost/location'},
        {'latitude': 999, 'longitude': 79, 'location_source_url':'https://example.org'}
    ]:
        with pytest.raises(ValidationError):
            listings.ListingWrite.model_validate({**BASE, **changes})


def test_public_payload_keeps_private_revision_out():
    item = ServiceListing(id=uuid.uuid4(), organization_id=uuid.uuid4(),slug='published',
                          category='accommodation',title='Live',summary='Live summary',description='Live description',
                          district='Kandy',province='Central',status='published',details=BASE['details'])
    item.photos=[]
    item.revisions=[]
    item.latitude = 7.2; item.longitude = 80.6
    item.location_source_url = 'https://www.openstreetmap.org'; item.location_note = 'Provider reference point'
    private = listings.ServiceListingRevision(id=uuid.uuid4(),listing_id=item.id,author_id=uuid.uuid4(),
                                              status='submitted',snapshot=BASE)
    item.revisions.append(private)
    payload = listings.listing_dict(item)
    assert payload['latitude'] == 7.2
    assert all(key not in payload for key in ('revision','review_feedback','organization_id','author_id'))
    assert listings._private_dict(item)['revision']['status'] == 'submitted'


def test_saving_a_revision_never_edits_the_live_listing(monkeypatch):
    user = User(id=uuid.uuid4(), status='active')
    org = VendorOrganization(id=uuid.uuid4(),owner_id=user.id,verification_state='approved')
    item = ServiceListing(id=uuid.uuid4(), organization_id=org.id,status='published',
                          category='accommodation', title='Live listing', details=BASE['details'])
    item.photos=[];item.revisions=[]
    monkeypatch.setattr(listings,'_member_listing',lambda *args, **kwargs:(org,item))
    db = Mock(); db.scalar.return_value=item.id
    proposed = listings.ListingRevisionWrite.model_validate({**BASE, 'title':'Revised family rooms', 'photos':[]})
    result = listings.save_revision(org.id,item.id,proposed,user,db)
    assert result['status']=='draft'
    assert item.title=='Live listing' and item.status=='published'
    assert result['snapshot']['title']=='Revised family rooms'
    assert result['snapshot']['photos']==[]
    db.commit.assert_called_once()


def test_revision_approval_is_independent_and_atomic():
    admin = User(id=uuid.uuid4(),status='active')
    owner = uuid.uuid4();org = VendorOrganization(id=uuid.uuid4(),owner_id=owner,verification_state='approved')
    item = ServiceListing(id=uuid.uuid4(),organization_id=org.id,status='published',
                          category='accommodation',title='Live title',details=BASE['details'])
    item.photos=[];item.revisions=[]
    snapshot = listings.ListingRevisionWrite.model_validate({**BASE, 'title':'New approved title',
        'photos':[]}).model_dump(mode='json')
    rev = ServiceListingRevision(id=uuid.uuid4(),listing_id=item.id,author_id=owner,
                                 status='submitted',snapshot=snapshot)
    db=Mock();db.scalar.side_effect=[rev,item,None,None];db.get.return_value=org
    decision=listings.RevisionDecision(decision='approved',reason='Verified each claim and the business registration')
    result=listings.decide_revision(rev.id,decision,admin,db)
    assert result['status']=='approved'
    assert item.title=='New approved title'
    assert item.status=='published'
    assert rev.reviewer_id==admin.id
    db.flush.assert_called_once()
    db.commit.assert_called_once()


def test_admin_must_not_review_owned_business_revisions():
    admin=User(id=uuid.uuid4(),status='active')
    org=VendorOrganization(id=uuid.uuid4(),owner_id=admin.id,verification_state='approved')
    item=ServiceListing(id=uuid.uuid4(),organization_id=org.id,status='published')
    rev=ServiceListingRevision(id=uuid.uuid4(),listing_id=item.id,status='submitted')
    db=Mock();db.scalar.side_effect=[rev,item];db.get.return_value=org
    with pytest.raises(HTTPException) as exc:
        listings.decide_revision(rev.id,listings.RevisionDecision(decision='approved',reason='Reviewed submitted update independently'),admin,db)
    assert exc.value.status_code==403
    db.commit.assert_not_called()


def test_unauthenticated_users_cannot_manage_revisions():
    org=uuid.uuid4(); item=uuid.uuid4(); rev=uuid.uuid4()
    with TestClient(app) as client:
        assert client.post(f'/api/v1/vendor/organizations/{org}/listings/{item}/revisions',json=BASE).status_code==401
        assert client.post(f'/api/v1/vendor/organizations/{org}/listings/{item}/revisions/submit').status_code==401
        assert client.get('/api/v1/admin/listings/revisions').status_code==401
        assert client.post(f'/api/v1/admin/listings/revisions/{rev}/decision',json={}).status_code==401


def test_migration_is_additive_and_revision_model_exists():
    path = Path(__file__).parents[1]/'migrations'/'versions'/'0011_advanced_listings.py'
    spec=importlib.util.spec_from_file_location('advanced_listings_migration',path)
    module=importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    assert module.revision=='0011_advanced_listings'
    assert module.down_revision=='0010_service_listings'
    assert ServiceListingRevision.__tablename__=='service_listing_revisions'
    assert 'location_source_url' in ServiceListing.__table__.columns
