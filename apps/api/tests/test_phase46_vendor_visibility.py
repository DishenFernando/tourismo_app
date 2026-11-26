"""Pre-Phase-5 change: content publication is separate from verification badges."""
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.dialects.postgresql import dialect

from tourismo.core.models import ServiceListing, VendorOrganization
from tourismo.listings.routes import _public_query, _publishable_org, listing_dict


def sample_org(state: str):
    return VendorOrganization(id=uuid4(), owner_id=uuid4(), business_name='Test Business',
                              category='restaurant', contact_email='contact@example.test',
                              verification_state=state)


def test_business_can_seek_listing_publication_before_verification():
    for state in ('draft', 'submitted', 'changes_requested', 'approved'):
        db = Mock()
        db.scalar.return_value = None
        _publishable_org(sample_org(state), db)


def test_rejected_or_expired_business_must_not_publish():
    for state in ('rejected', 'expired_license'):
        with pytest.raises(HTTPException) as error:
            _publishable_org(sample_org(state), Mock())
        assert error.value.status_code == 409


def test_expired_evidence_suppresses_visibility_and_blocks_new_publication():
    db = Mock()
    db.scalar.return_value = uuid4()
    with pytest.raises(HTTPException) as error:
        _publishable_org(sample_org('approved'), db)
    assert error.value.status_code == 409
    statement = str(_public_query().compile(dialect=dialect()))
    assert 'vendor_evidence.expires_on' in statement
    assert 'NOT (EXISTS' in statement


def test_public_sql_filters_only_published_eligible_businesses_not_approved_only():
    statement = str(_public_query().compile(dialect=dialect(), compile_kwargs={'literal_binds': True}))
    assert "service_listings.status = 'published'" in statement
    assert "vendor_organizations.verification_state NOT IN ('rejected', 'expired_license')" in statement
    assert "vendor_organizations.verification_state = 'approved'" not in statement


def test_badge_is_server_computed_from_org_state_and_no_private_fields():
    for state, expected in (('approved', True), ('submitted', False), ('draft', False)):
        item=ServiceListing(id=uuid4(), slug='test', organization_id=uuid4(),
                            category='restaurant', title='Test Service', summary='Example',
                            description='More details', province='Central', district='Kandy',
                            details={'cuisines':['local']},status='published')
        item.photos = []
        item.organization = sample_org(state)
        result=listing_dict(item)
        assert result['business_verified'] is expected
        assert result['business_name']=='Test Business'
        assert 'verification_state' not in result and 'license_no' not in result
        assert 'owner_id' not in result and 'organization_id' not in result
