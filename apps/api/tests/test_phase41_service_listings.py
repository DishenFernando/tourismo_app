"""Phase 4.1 access isolation, validation, integrity and migration contract."""
import importlib.util
import uuid
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql

from tourismo.core.models import (
    ServiceListing, ServiceListingPhoto, ServiceListingReview, User, VendorOrganization,
)
from tourismo.listings.routes import (
    AccommodationDetails, ListingDecision, ListingWrite, PhotoWrite, admin_decide_listing,
    listing_dict, validate_details, _draft, _publishable_org, _public_query,
)
from tourismo.main import app


VALID = dict(title='Comfortable garden guesthouse', summary='Quiet rooms near the historic town center.',
             description='A locally operated property with several private rooms for visiting families. '
                         'Please contact us for confirmed rates, child policies, and dates.',
             public_email='hello@example.com', public_phone=None,
             details={'room_types':[{'name':'Family room', 'max_adults':2, 'max_children':2,
                                     'number_of_rooms':3, 'indicative_nightly_lkr_minor':1500000}],
                      'amenities':['Wi-Fi'], 'house_rules':'No smoking'})


def test_category_schemas_enforce_occupancy_menu_and_vehicle_constraints():
    assert validate_details('accommodation', VALID['details'])['room_types'][0]['max_children'] == 2
    with pytest.raises(HTTPException) as exc:
        validate_details('accommodation', {'room_types':[{'name':'Two', 'max_adults':0, 'max_children':2, 'number_of_rooms':1}]})
    assert exc.value.status_code == 422
    with pytest.raises(HTTPException):
        validate_details('restaurant', {'cuisines':[], 'menu_items':[]})
    with pytest.raises(HTTPException):
        validate_details('transport', {'vehicle_types':[{'name':'Van', 'passenger_seats':0, 'luggage_bags':3}], 'service_areas':['Kandy']})
    with pytest.raises(HTTPException):
        validate_details('guide', {'languages':['English'], 'service_areas':['Kandy'], 'unexpected_flag':True})
    assert validate_details('activity', {'experience_types':['Hiking'], 'service_areas':['Ella']})


def test_public_contacts_and_credited_photo_validation():
    assert ListingWrite.model_validate(VALID).public_email == 'hello@example.com'
    with pytest.raises(ValidationError):
        ListingWrite.model_validate({**VALID, 'public_email':'invalid'})
    with pytest.raises(ValidationError):
        ListingWrite.model_validate({**VALID,'registration_no':'secret'})
    photo=dict(image_url='https://upload.wikimedia.org/wikipedia/commons/photo.jpg',
               source_url='https://commons.wikimedia.org/wiki/File:photo.jpg',
               credit='Tourismo Photographer',license_name='CC BY 4.0',
               license_url='https://creativecommons.org/licenses/by/4.0/',alt_text='Licensed guesthouse photo')
    assert PhotoWrite.model_validate(photo).credit == 'Tourismo Photographer'
    for invalid_url in ['http://insecure.example/image.jpg','https://localhost/image.jpg',
                        'https://example.com:invalid/image.jpg','https://user:pass@example.com/image.jpg']:
        with pytest.raises(ValidationError):
            PhotoWrite.model_validate({**photo,'image_url':invalid_url})


def test_only_posted_public_fields_are_exposed():
    listing = ServiceListing(id=uuid.uuid4(), organization_id=uuid.uuid4(), slug='demo',
        category='accommodation', title='Demo', summary='User entered description',
        description='A full user entered description',province='Southern',district='Galle',
        public_email=None,public_phone='+94112223344',details=VALID['details'], status='published')
    listing.photos=[]
    public = listing_dict(listing)
    assert public['booking_available'] is False and public['prices_are_indicative'] is True
    assert all(k not in public for k in ('organization_id','registration_no','operating_address','review_feedback','license_no','owner_id'))
    assert public['public_phone'] == '+94112223344'


def test_published_cannot_be_edited_and_review_reasons_required():
    listing=ServiceListing(status='published')
    with pytest.raises(HTTPException) as exc:
        _draft(listing)
    assert exc.value.status_code == 409
    assert ListingDecision(decision='published',reason='Verified provider and details independently').decision == 'published'
    with pytest.raises(ValidationError):
        ListingDecision(decision='published',reason='okay')
    with pytest.raises(ValidationError):
        ListingDecision(decision='deleted',reason='Reviewed independently by staff')


def test_public_query_requires_approved_org_and_no_expired_license():
    statement=str(_public_query().compile(dialect=postgresql.dialect()))
    assert 'service_listings.status' in statement
    assert 'vendor_organizations.verification_state' in statement
    assert 'vendor_evidence.expires_on' in statement
    assert 'NOT (EXISTS' in statement


def test_guest_can_search_but_anonymous_cannot_create_or_moderate():
    paths={route.path for route in app.routes}
    assert '/api/v1/listings' in paths
    assert '/api/v1/listings/{slug}' in paths
    assert '/api/v1/vendor/organizations/{org_id}/listings' in paths
    assert '/api/v1/admin/listings/{listing_id}/decision' in paths
    org=uuid.uuid4(); listing=uuid.uuid4()
    with TestClient(app) as client:
        assert client.get(f'/api/v1/vendor/organizations/{org}/listings').status_code==401
        assert client.post(f'/api/v1/vendor/organizations/{org}/listings',json=VALID).status_code==401
        assert client.post(f'/api/v1/vendor/organizations/{org}/listings/{listing}/submit').status_code==401
        assert client.get('/api/v1/admin/listings').status_code==401
        assert client.post(f'/api/v1/admin/listings/{listing}/decision',json={}).status_code==401
        assert client.get('/api/v1/health/live').status_code==200


def test_admin_cannot_self_approve_a_submitted_listing():
    admin=User(id=uuid.uuid4(), status='active')
    org=VendorOrganization(id=uuid.uuid4(),owner_id=admin.id, verification_state='approved')
    listing=ServiceListing(id=uuid.uuid4(),organization_id=org.id,status='submitted')
    db=Mock()
    db.scalar.return_value=listing
    db.get.return_value=org
    with pytest.raises(HTTPException) as exc:
        admin_decide_listing(listing.id,ListingDecision(decision='published',reason='Reviewed full provider claim and contacts'),admin,db)
    assert exc.value.status_code == 403
    db.commit.assert_not_called()


def test_business_verification_is_separate_from_listing_content_review():
    db=Mock()
    db.scalar.return_value=None
    org=VendorOrganization(id=uuid.uuid4(),verification_state='submitted')
    _publishable_org(org, db)  # An unverified business may request listing review.
    org.verification_state='rejected'
    with pytest.raises(HTTPException) as exc:
        _publishable_org(org, db)
    assert exc.value.status_code == 409


def test_migration_is_additive_and_model_tables_are_present():
    path=Path(__file__).parents[1]/'migrations'/'versions'/'0010_service_listings.py'
    spec=importlib.util.spec_from_file_location('tourismo_listing_migration',path)
    module=importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    assert module.revision == '0010_service_listings'
    assert module.down_revision == '0009_vendor_documents'
    for name in ['service_listings','service_listing_photos','service_listing_reviews']:
        assert name in ServiceListing.metadata.tables
    assert ServiceListingPhoto.__tablename__=='service_listing_photos'
    assert ServiceListingReview.__tablename__=='service_listing_reviews'
