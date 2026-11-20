"""Phase 4.5: title-only private listing creation without weakening publication gate."""
from unittest.mock import MagicMock
from types import SimpleNamespace
import uuid

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from tourismo.main import app
from tourismo.core.models import ServiceListing, VendorOrganization
from tourismo.listings import routes


def test_quick_start_requires_title_and_rejects_extra_fields():
    assert routes.QuickStartListing.model_validate({'title': '  Mountain Hut  '}).title == 'Mountain Hut'
    for bad in [{'title': '  '}, {'title': 'A'}, {'title': 'Demo', 'status': 'published'}]:
        with pytest.raises(ValidationError):
            routes.QuickStartListing.model_validate(bad)


def test_guest_cannot_create_a_private_starter():
    with TestClient(app) as client:
        org_id = uuid.uuid4()
        assert client.post(f'/api/v1/vendor/organizations/{org_id}/listings/quick-start',
                           json={'title': 'Test stay'}).status_code == 401


def test_quick_start_creates_private_incomplete_draft(monkeypatch):
    user = SimpleNamespace(id=uuid.uuid4())
    org = VendorOrganization(id=uuid.uuid4(), owner_id=user.id,
                             category='accommodation', business_name='Sample',
                             verification_state='draft', province=None, district=None)
    db = MagicMock()
    db.scalar.return_value = 0
    monkeypatch.setattr(routes,'_organization',lambda *_args,**_kwargs:org)
    monkeypatch.setattr(routes,'_event',lambda *_args,**_kwargs:None)
    created = []
    db.add.side_effect = lambda value: created.append(value)
    monkeypatch.setattr(routes,'_private_dict',lambda item:{'status':item.status,'title':item.title,'details':item.details})
    data=routes.create_quick_listing(org.id, routes.QuickStartListing(title='Demo mountain stay'),user,db)
    assert data['status']=='draft' and data['title']=='Demo mountain stay'
    assert data['details']=={}
    assert created and isinstance(created[0],ServiceListing)
    assert created[0].province=='' and created[0].district==''
    db.commit.assert_called_once()


def test_quick_start_respects_business_listing_quota(monkeypatch):
    user = SimpleNamespace(id=uuid.uuid4())
    org = VendorOrganization(id=uuid.uuid4(), owner_id=user.id, category='accommodation')
    monkeypatch.setattr(routes,'_organization',lambda *_a,**_k:org)
    db=MagicMock(); db.scalar.return_value=25
    with pytest.raises(HTTPException) as exc:
        routes.create_quick_listing(org.id,routes.QuickStartListing(title='Hill view stay'),user,db)
    assert exc.value.status_code==409
    db.add.assert_not_called()


def test_incomplete_draft_cannot_be_submitted_even_after_organization_approval(monkeypatch):
    user=SimpleNamespace(id=uuid.uuid4())
    org=VendorOrganization(id=uuid.uuid4(), owner_id=user.id, category='restaurant', verification_state='approved')
    listing=ServiceListing(id=uuid.uuid4(),organization_id=org.id, category='restaurant', status='draft',
                           title='Quick example',summary='',description='',details={}, public_email='vendor@example.com')
    db=MagicMock()
    monkeypatch.setattr(routes,'_member_listing',lambda *_a,**_k:(org,listing))
    monkeypatch.setattr(routes,'_approved_org',lambda *_a,**_k:None)
    with pytest.raises(HTTPException) as exc:
        routes.submit_listing(org.id,listing.id,user,db)
    assert exc.value.status_code==422
    assert listing.status=='draft'
    db.commit.assert_not_called()
