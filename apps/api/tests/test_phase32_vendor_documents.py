"""Phase 3.2 regression and security checks. Database acceptance uses disposable Postgres."""
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4
import importlib.util

import pytest
from fastapi import HTTPException, UploadFile
from fastapi.testclient import TestClient

from tourismo.main import app
from tourismo.vendors import documents
from tourismo.core.models import VendorDocument


PNG = b'\x89PNG\r\n\x1a\n' + b'\x00' * 20 + b'\x00\x00\x00\x00IEND\xaeB`\x82'
PDF = b'%PDF-1.7\n1 0 obj\n<<>>\nendobj\n%%EOF\n'


def test_file_signature_extension_and_content_type_must_agree():
    assert documents.classify_file('license.pdf', 'application/pdf', PDF[:32], PDF[-1024:]) == 'application/pdf'
    assert documents.classify_file('photo.png', 'image/png', PNG[:32], PNG[-1024:]) == 'image/png'
    with pytest.raises(HTTPException) as exc:
        documents.classify_file('license.pdf', 'application/pdf', PNG[:32], PNG)
    assert exc.value.status_code == 415
    with pytest.raises(HTTPException):
        documents.classify_file('../../license.svg', 'image/svg+xml', b'<svg', b'</svg>')
    with pytest.raises(HTTPException):
        documents.classify_file('file.pdf', 'image/png', PDF[:32], PDF)


def test_unscanned_attachment_must_never_download():
    pending = VendorDocument(id=uuid4(), organization_id=uuid4(), evidence_id=uuid4(),
                             uploaded_by=uuid4(), storage_key='a'*32, original_name='safe.pdf',
                             scan_state='pending_scan', media_type='application/pdf', sha256='f'*64,
                             size_bytes=10)
    with pytest.raises(HTTPException) as exc:
        documents._download(pending)
    assert exc.value.status_code == 423
    pending.scan_state = 'infected'
    with pytest.raises(HTTPException):
        documents._download(pending)


def test_anonymous_document_routes_reject_requests():
    paths={route.path for route in app.routes}
    assert '/api/v1/vendor/organizations/{org_id}/documents' in paths
    assert '/api/v1/admin/vendor-verifications/{org_id}/documents' in paths
    with TestClient(app) as client:
        org=str(uuid4()); doc=str(uuid4())
        assert client.get(f'/api/v1/vendor/organizations/{org}/documents').status_code == 401
        assert client.post(f'/api/v1/vendor/organizations/{org}/documents').status_code == 401
        assert client.get(f'/api/v1/vendor/organizations/{org}/documents/{doc}/download').status_code == 401
        assert client.delete(f'/api/v1/vendor/organizations/{org}/documents/{doc}').status_code == 401
        assert client.get(f'/api/v1/admin/vendor-verifications/{org}/documents').status_code == 401
        assert client.get(f'/api/v1/admin/vendor-verifications/{org}/documents/{doc}/download').status_code == 401


@pytest.mark.asyncio
async def test_upload_limits_and_pending_scan_fail_closed(monkeypatch, tmp_path):
    org=SimpleNamespace(id=uuid4(),verification_state='draft')
    user=SimpleNamespace(id=uuid4())
    evidence_id=uuid4()
    monkeypatch.setattr(documents, '_organization', lambda *args,**kwargs:org)
    monkeypatch.setattr(documents, 'private_directory', lambda:tmp_path)
    monkeypatch.setattr(documents, '_event', lambda *args,**kwargs:None)
    monkeypatch.setattr(documents, 'scan_with_clamav', lambda _: 'pending_scan')
    db=MagicMock()
    db.scalar.side_effect=[0,evidence_id]
    result=await documents.upload_document(org.id,evidence_id,UploadFile(filename='permit.pdf',file=BytesIO(PDF),headers={'content-type':'application/pdf'}),user,db)
    assert result['scan_state']=='pending_scan' and result['downloadable'] is False
    assert len(list(tmp_path.iterdir()))==1
    db.commit.assert_called_once()
    db.scalar.side_effect=[0,evidence_id]
    oversized=UploadFile(filename='huge.pdf',file=BytesIO(b'%PDF-1.7'+b'A'*(documents.MAX_BYTES+1)+b'%%EOF'),headers={'content-type':'application/pdf'})
    with pytest.raises(HTTPException) as exc:
        await documents.upload_document(org.id,evidence_id,oversized,user,db)
    assert exc.value.status_code==413
    assert len(list(tmp_path.iterdir()))==1  # oversized bytes cleaned up


def test_migration_preserves_existing_tables_and_adds_expiry_state():
    location=Path(__file__).parents[1]/'migrations'/'versions'/'0009_vendor_documents.py'
    spec=importlib.util.spec_from_file_location('vendor_document_migration',location)
    m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    assert m.down_revision=='0008_vendor_onboarding'
    names=[]
    m.op.create_table=lambda name,*args,**kw:names.append(name)
    m.op.create_index=lambda *args,**kw:None
    m.op.drop_constraint=lambda *args,**kw:None
    m.op.create_check_constraint=lambda *args,**kw:None
    m.upgrade()
    assert names==['vendor_documents']


def test_scan_unavailable_is_never_reported_clean(monkeypatch, tmp_path):
    data=tmp_path/'vendor.pdf';data.write_bytes(PDF)
    monkeypatch.setattr(documents, 'get_settings',lambda:SimpleNamespace(vendor_clamav_host='',vendor_clamav_port=3310))
    assert documents.scan_with_clamav(data)=='pending_scan'


def test_production_vendor_review_requires_recent_clerk_mfa(monkeypatch):
    from tourismo.identity import security
    from fastapi import HTTPException
    monkeypatch.setattr(security, 'get_settings', lambda: SimpleNamespace(app_environment='production'))
    for age in (None, 11):
        with pytest.raises(HTTPException) as exc:
            security.require_privileged_mfa(security.VerifiedIdentity('user_test','sess_test', age))
        assert exc.value.status_code == 403
    recent = security.VerifiedIdentity('user_test', 'sess_test', 5)
    assert security.require_privileged_mfa(recent) is recent
    monkeypatch.setattr(security, 'get_settings', lambda: SimpleNamespace(app_environment='development'))
    assert security.require_privileged_mfa(security.VerifiedIdentity('user_test','sess_test'))


def test_expiry_marks_approved_organization_and_records_audit():
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session
    from tourismo.core.database import Base
    from tourismo.core.models import User, VendorOrganization, VendorEvidence, AuditEvent
    from tourismo.vendors.operations import expire_licenses
    from datetime import date, timedelta
    engine = create_engine('sqlite+pysqlite:///:memory:')
    Base.metadata.create_all(engine, tables=[User.__table__,VendorOrganization.__table__,
        VendorEvidence.__table__,AuditEvent.__table__])
    with Session(engine) as db:
        user=User(auth_subject='test-expiry',status='active')
        db.add(user);db.flush()
        org=VendorOrganization(owner_id=user.id,category='restaurant',business_name='Small test restaurant',
            contact_email='a@b.com',province='Western',district='Colombo',operating_address='Test Street',
            verification_state='approved')
        db.add(org);db.flush()
        db.add(VendorEvidence(organization_id=org.id,evidence_type='business_registration',
            issuer='Registry',reference_number='X102',expires_on=date.today()-timedelta(days=1)))
        db.commit()
        assert expire_licenses(db)==1
        db.refresh(org)
        assert org.verification_state=='expired_license'
        assert expire_licenses(db)==0  # idempotent
        assert len(db.scalars(select(AuditEvent)).all())==1
