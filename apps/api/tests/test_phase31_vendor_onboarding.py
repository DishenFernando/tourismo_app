"""Phase 3.1 validation, anonymous access, and guarded disposable-DB workflow."""
import importlib.util
import os
import uuid
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select, delete

from tourismo.main import app
from tourismo.core.models import VendorOrganization, User, AuditEvent
from tourismo.vendors.routes import (
    VendorCreate, VendorEdit, EvidenceCreate, MemberInvite, VerificationDecision,
    organization_dict, _editable, _organization,
)
from tourismo.core.database import get_db
from tourismo.identity.security import require_user


VALID = dict(category='restaurant',business_name='  Kandy Family Cafe  ',
    registration_no=' PV  567 ',contact_email=' INFO@EXAMPLE.COM ',contact_phone='+94 777 555 444',
    province='Central',district='Kandy',operating_address='Old Peradeniya Road, Kandy',license_no=None)


def test_vendor_input_validation_normalizes_and_rejects_privilege_fields():
    body=VendorCreate.model_validate(VALID)
    assert body.registration_no=='PV 567'
    assert body.business_name=='Kandy Family Cafe'
    assert body.contact_email=='info@example.com'
    with pytest.raises(ValueError):
        VendorCreate.model_validate({**VALID,'verification_state':'approved'})
    with pytest.raises(ValueError):
        VendorCreate.model_validate({**VALID,'owner_id':str(uuid.uuid4())})
    with pytest.raises(ValueError):
        VendorCreate.model_validate({**VALID,'category':'super_admin'})
    with pytest.raises(ValueError):
        VendorCreate.model_validate({**VALID,'contact_email':'bad-email'})
    edited=VendorEdit.model_validate({'registration_no':'pv   567'})
    assert 'registration_no' in edited.model_dump(exclude_unset=True)
    with pytest.raises(ValueError):
        VendorEdit.model_validate({'business_name':None})
    with pytest.raises(ValueError):
        MemberInvite.model_validate({'user_id':str(uuid.uuid4()),'role':'owner'})


def test_vendor_evidence_and_verification_require_manual_checks():
    evidence=EvidenceCreate.model_validate(dict(evidence_type='tourism_license',issuer='SLTDA',reference_number='T123'))
    assert evidence.expires_on is None
    with pytest.raises(ValueError):
        EvidenceCreate.model_validate(dict(evidence_type='bank_statement',issuer='Bank',reference_number='123'))
    with pytest.raises(ValueError):
        VerificationDecision.model_validate(dict(decision='approved',reason='Checked the submitted registry evidence'))
    with pytest.raises(ValueError):
        VerificationDecision.model_validate(dict(decision='approved',reason='Checked the submitted registry evidence',source_url='http://unsafe.example'))
    with pytest.raises(ValueError):
        VerificationDecision.model_validate(dict(decision='approved',reason='     ',source_url='https://www.sltda.gov.lk/'))
    decision=VerificationDecision.model_validate(dict(decision='approved',reason='Registry details checked against external source',source_url='https://www.sltda.gov.lk/'))
    assert decision.decision=='approved'


def test_only_private_vendor_routes_are_defined_and_anonymous_is_rejected():
    paths={route.path for route in app.routes}
    assert '/api/v1/vendor/organizations' in paths
    assert '/api/v1/vendor/organizations/{org_id}/evidence' in paths
    assert '/api/v1/admin/vendor-verifications/{org_id}/decision' in paths
    with TestClient(app) as client:
        assert client.get('/api/v1/vendor/organizations').status_code==401
        assert client.post('/api/v1/vendor/organizations',json=VALID).status_code==401
        assert client.get('/api/v1/vendor/organizations/'+str(uuid.uuid4())).status_code==401
        assert client.post('/api/v1/vendor/organizations/'+str(uuid.uuid4())+'/submit').status_code==401
        assert client.get('/api/v1/vendor/invitations').status_code==401
        assert client.get('/api/v1/admin/vendor-verifications').status_code==401
        assert client.post('/api/v1/admin/vendor-verifications/'+str(uuid.uuid4())+'/decision',json={}).status_code==401
        assert client.get('/api/v1/health/live').status_code==200  # guests still access the public app
        assert '/api/v1/destinations' in paths


def test_approved_organization_is_immutable_without_new_verification():
    record=VendorOrganization(id=uuid.uuid4(),owner_id=uuid.uuid4(),verification_state='approved')
    with pytest.raises(HTTPException) as exc:
        _editable(record)
    assert exc.value.status_code==409
    record.verification_state='draft'
    _editable(record)
    data=organization_dict(record)
    assert data['has_public_listing'] is False
    assert data['subscription_trial_started'] is False
    assert not hasattr(record,'password')


def test_migration_is_additive_and_down_revision_is_phase25():
    path=Path(__file__).parents[1]/'migrations'/'versions'/'0008_vendor_onboarding.py'
    spec=importlib.util.spec_from_file_location('tourismo_vendor_migration',path)
    module=importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    assert module.revision=='0008_vendor_onboarding'
    assert module.down_revision=='0007_pilot_destination_guides'
    class Recorder:
        def __init__(self): self.tables=[]
        def create_table(self,name,*a,**kw):self.tables.append(name)
        def create_index(self,*a,**kw):pass
    recorder=Recorder()
    module.op.create_table=recorder.create_table
    module.op.create_index=recorder.create_index
    module.upgrade()
    assert recorder.tables==['vendor_organizations','vendor_memberships','vendor_evidence','vendor_verification_checks']
    assert all(name not in recorder.tables for name in ['users','trips','destinations'])


@pytest.mark.skipif(not os.environ.get('TEST_DATABASE_URL'),reason='Requires a migrated disposable PostgreSQL test database')
def test_vendor_onboarding_tenant_isolation_and_independent_approval():
    """Exercises real DB constraints, ownership checks, manual verification and audit."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from tourismo.admin.permissions import require_admin
    engine=create_engine(os.environ['TEST_DATABASE_URL'])
    user_a=User(id=uuid.uuid4(),auth_subject=f'test-vendor-A-{uuid.uuid4().hex}',status='active')
    user_b=User(id=uuid.uuid4(),auth_subject=f'test-vendor-B-{uuid.uuid4().hex}',status='active')
    admin=User(id=uuid.uuid4(),auth_subject=f'test-vendor-admin-{uuid.uuid4().hex}',status='active')
    with Session(engine) as db:
        db.add_all([user_a,user_b,admin]);db.commit()
    def db_for_test():
        with Session(engine,autoflush=False,expire_on_commit=False) as db:
            yield db
    app.dependency_overrides[get_db]=db_for_test
    app.dependency_overrides[require_user]=lambda:user_a
    app.dependency_overrides[require_admin]=lambda:admin
    try:
        with TestClient(app) as client:
            application={**VALID,'registration_no':'PV-'+uuid.uuid4().hex[:10]}
            created=client.post('/api/v1/vendor/organizations',json=application)
            assert created.status_code==201,created.text
            org_id=created.json()['id']
            assert created.json()['verification_state']=='draft'
            assert created.json()['has_public_listing'] is False
            assert len(client.get('/api/v1/vendor/organizations').json())==1
            assert client.post(f'/api/v1/vendor/organizations/{org_id}/submit').status_code==422
            evidence=client.post(f'/api/v1/vendor/organizations/{org_id}/evidence',json={
                'evidence_type':'business_registration','issuer':'Official registry','reference_number':'REF-'+uuid.uuid4().hex[:10]})
            assert evidence.status_code==201,evidence.text
            submit=client.post(f'/api/v1/vendor/organizations/{org_id}/submit')
            assert submit.status_code==200,submit.text
            assert submit.json()['verification_state']=='submitted'
            assert client.patch(f'/api/v1/vendor/organizations/{org_id}',json={'business_name':'Changed'}).status_code==409
            app.dependency_overrides[require_user]=lambda:user_b
            assert client.get(f'/api/v1/vendor/organizations/{org_id}').status_code==404
            assert client.get('/api/v1/vendor/organizations') .json()==[]
            assert client.post(f'/api/v1/vendor/organizations/{org_id}/submit').status_code==404
            app.dependency_overrides[require_admin]=lambda:user_a
            no_self=client.post(f'/api/v1/admin/vendor-verifications/{org_id}/decision',json={
                'decision':'approved','reason':'External registration checked successfully','source_url':'https://www.sltda.gov.lk/'})
            assert no_self.status_code==403
            app.dependency_overrides[require_admin]=lambda:admin
            approved=client.post(f'/api/v1/admin/vendor-verifications/{org_id}/decision',json={
                'decision':'approved','reason':'External registration checked successfully','source_url':'https://www.sltda.gov.lk/'})
            assert approved.status_code==200,approved.text
            assert approved.json()['verification_state']=='approved'
            assert approved.json()['subscription_trial_started'] is False
            assert client.post(f'/api/v1/admin/vendor-verifications/{org_id}/decision',json={
                'decision':'approved','reason':'Duplicate approval should be blocked','source_url':'https://www.sltda.gov.lk/'}).status_code==409
            details=client.get(f'/api/v1/admin/vendor-verifications/{org_id}').json()
            assert len(details['history'])==1
    finally:
        app.dependency_overrides.clear()
        with Session(engine) as db:
            orgs=db.scalars(select(VendorOrganization).where(VendorOrganization.owner_id==user_a.id)).all()
            db.execute(delete(AuditEvent).where(AuditEvent.actor_id.in_([user_a.id, user_b.id, admin.id])))
            for o in orgs: db.delete(o)
            db.flush()
            for u in (user_a,user_b,admin): db.delete(db.get(User,u.id))
            db.commit()
        engine.dispose()
