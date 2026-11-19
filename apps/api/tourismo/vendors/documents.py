"""Private vendor evidence attachments; no public file routes or unscanned downloads.

Development storage is a Docker volume. Production MUST use hardened private object storage
and a malware scanner before enabling uploads on a multi-instance deployment.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import socket
import struct
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tourismo.admin.permissions import require_admin
from tourismo.core.config import get_settings
from tourismo.core.database import get_db
from tourismo.core.models import User, VendorDocument, VendorEvidence, VendorOrganization, now_utc
from tourismo.identity.security import require_user, require_privileged_mfa
from tourismo.vendors.routes import _editable, _event, _organization

router = APIRouter(prefix='/api/v1/vendor/organizations', tags=['vendor-private-documents'])
admin_router = APIRouter(prefix='/api/v1/admin/vendor-verifications', tags=['vendor-private-documents'])
MAX_BYTES = 5 * 1024 * 1024
MAX_DOCUMENTS = 12
TYPES = {'.pdf': 'application/pdf', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg'}


def classify_file(name: str, supplied_type: str | None, head: bytes, tail: bytes) -> str:
    """Require an allowed extension, declared content type and genuine file signature.

    Signatures are a filter, not a malware assessment. ClamAV must confirm cleanliness.
    """
    suffix = Path(name).suffix.lower()
    expected = TYPES.get(suffix)
    if not expected or supplied_type != expected:
        raise HTTPException(415, 'Only PDF, PNG and JPEG evidence documents are accepted')
    valid = ((expected == 'application/pdf' and head.startswith(b'%PDF-') and b'%%EOF' in tail)
             or (expected == 'image/png' and head.startswith(b'\x89PNG\r\n\x1a\n') and b'IEND' in tail)
             or (expected == 'image/jpeg' and head.startswith(b'\xff\xd8\xff') and tail.endswith(b'\xff\xd9')))
    if not valid:
        raise HTTPException(415, 'File contents do not match a valid supported format')
    return expected


def private_directory() -> Path:
    settings = get_settings()
    if settings.app_environment.lower() == 'production':
        # A local volume cannot safely provide durability or private multi-replica access
        # on cloud application platforms such as Render. Use private object storage there.
        raise HTTPException(503, 'Production document storage is not configured')
    root = Path(settings.vendor_document_dir).resolve()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    return root


def scan_with_clamav(path: Path) -> str:
    """ClamAV INSTREAM over an internal TCP connection; unavailable == pending.

    Do not treat an unavailable scanner as success. No user-controlled host is accepted.
    """
    settings = get_settings()
    if not settings.vendor_clamav_host:
        return 'pending_scan'
    try:
        with socket.create_connection((settings.vendor_clamav_host, settings.vendor_clamav_port), timeout=4) as conn:
            conn.settimeout(25)
            conn.sendall(b'zINSTREAM\x00')
            with path.open('rb') as stream:
                while chunk := stream.read(64 * 1024):
                    conn.sendall(struct.pack('!I', len(chunk)) + chunk)
            conn.sendall(struct.pack('!I', 0))
            response = conn.recv(4096).decode('utf-8', errors='replace')
            if ' FOUND' in response:
                return 'infected'
            if ' OK' in response:
                return 'clean'
    except (OSError, ValueError, TimeoutError):
        pass
    return 'pending_scan'


def document_dict(doc: VendorDocument) -> dict:
    return dict(id=str(doc.id), evidence_id=str(doc.evidence_id), name=doc.original_name,
                media_type=doc.media_type, size_bytes=doc.size_bytes, scan_state=doc.scan_state,
                uploaded_at=doc.uploaded_at.isoformat() if doc.uploaded_at else None,
                downloadable=doc.scan_state == 'clean' and doc.deleted_at is None)


def _documents(db: Session, org_id: UUID) -> list[VendorDocument]:
    return list(db.scalars(select(VendorDocument).where(
        VendorDocument.organization_id == org_id, VendorDocument.deleted_at.is_(None))
        .order_by(VendorDocument.uploaded_at.desc())).all())


def _document(db: Session, org_id: UUID, doc_id: UUID) -> VendorDocument:
    doc = db.scalar(select(VendorDocument).where(VendorDocument.id == doc_id,
                    VendorDocument.organization_id == org_id, VendorDocument.deleted_at.is_(None)))
    if doc is None:
        raise HTTPException(404, 'Document not found')
    return doc


def _download(doc: VendorDocument) -> FileResponse:
    if doc.scan_state != 'clean':
        raise HTTPException(423, 'Document cannot be downloaded until an antivirus scan passes')
    path = private_directory() / doc.storage_key
    if not path.is_file():
        raise HTTPException(503, 'Private document is unavailable')
    digest = hashlib.sha256()
    with path.open('rb') as source:
        while chunk := source.read(64 * 1024):
            digest.update(chunk)
    if digest.hexdigest() != doc.sha256 or path.stat().st_size != doc.size_bytes:
        raise HTTPException(409, 'Document integrity check failed')
    return FileResponse(path, media_type='application/octet-stream', filename='vendor-evidence' +
                        ('.pdf' if doc.media_type == 'application/pdf' else '.png' if doc.media_type == 'image/png' else '.jpg'),
                        content_disposition_type='attachment',
                        headers={'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff',
                                 'Content-Security-Policy': 'sandbox'})


@router.get('/{org_id}/documents')
def list_documents(org_id: UUID, user: User = Depends(require_user), db: Session = Depends(get_db)):
    _organization(db, org_id, user, ('owner', 'manager'))
    return [document_dict(d) for d in _documents(db, org_id)]


@router.post('/{org_id}/documents', status_code=201)
async def upload_document(org_id: UUID, evidence_id: UUID = Form(...), file: UploadFile = File(...),
                          user: User = Depends(require_user), db: Session = Depends(get_db)):
    org = _organization(db, org_id, user, ('owner', 'manager'))
    _editable(org)
    if db.scalar(select(func.count()).select_from(VendorDocument).where(
        VendorDocument.organization_id == org_id, VendorDocument.deleted_at.is_(None))) >= MAX_DOCUMENTS:
        raise HTTPException(409, 'Maximum twelve active documents per organization')
    evidence = db.scalar(select(VendorEvidence.id).where(VendorEvidence.id == evidence_id,
                         VendorEvidence.organization_id == org_id))
    if evidence is None:
        raise HTTPException(404, 'Evidence reference not found')
    original = (file.filename or '').replace('\\', '/').split('/')[-1][:120]
    if not original or Path(original).suffix.lower() not in TYPES:
        raise HTTPException(415, 'Only PDF, PNG and JPEG files are accepted')
    if file.content_type != TYPES[Path(original).suffix.lower()]:
        raise HTTPException(415, 'File type does not match its extension')
    root = private_directory()
    key = uuid4().hex
    target = root / key
    digest = hashlib.sha256()
    size = 0
    head = b''
    tail = b''
    try:
        fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            while data := await file.read(64 * 1024):
                size += len(data)
                if size > MAX_BYTES:
                    raise HTTPException(413, 'Evidence document exceeds the 5 MB limit')
                if not head:
                    head = data[:32]
                tail = (tail + data)[-1024:]
                digest.update(data)
                stream.write(data)
        if size == 0:
            raise HTTPException(422, 'Empty evidence files are not accepted')
        media_type = classify_file(original, file.content_type, head, tail)
        state = scan_with_clamav(target)
        if state == 'infected':
            raise HTTPException(422, 'Evidence file failed security scanning')
        doc = VendorDocument(organization_id=org_id, evidence_id=evidence_id, uploaded_by=user.id,
                             original_name=original, storage_key=key, media_type=media_type,
                             sha256=digest.hexdigest(), size_bytes=size, scan_state=state)
        db.add(doc)
        db.flush()
        _event(db, user, 'vendor.document.uploaded', org, f'Document {doc.id}: {state}')
        db.commit()
        return document_dict(doc)
    except Exception:
        db.rollback()
        target.unlink(missing_ok=True)
        raise
    finally:
        await file.close()


@router.get('/{org_id}/documents/{doc_id}/download')
def download_document(org_id: UUID, doc_id: UUID, user: User = Depends(require_user), db: Session = Depends(get_db)):
    _organization(db, org_id, user, ('owner', 'manager'))
    return _download(_document(db, org_id, doc_id))


@router.delete('/{org_id}/documents/{doc_id}', status_code=204)
def delete_document(org_id: UUID, doc_id: UUID, user: User = Depends(require_user), db: Session = Depends(get_db)):
    org = _organization(db, org_id, user, ('owner', 'manager'))
    _editable(org)
    doc = _document(db, org_id, doc_id)
    doc.deleted_at = now_utc()
    _event(db, user, 'vendor.document.deleted', org, f'Document {doc.id}')
    db.commit()
    (private_directory() / doc.storage_key).unlink(missing_ok=True)


@admin_router.get('/{org_id}/documents')
def review_documents(org_id: UUID, admin: User = Depends(require_admin), db: Session = Depends(get_db),
                     _mfa=Depends(require_privileged_mfa)):
    org = db.get(VendorOrganization, org_id)
    if org is None:
        raise HTTPException(404, 'Organization not found')
    from tourismo.core.models import VendorMembership
    if org.owner_id == admin.id or db.scalar(select(VendorMembership.id).where(
        VendorMembership.organization_id == org_id, VendorMembership.user_id == admin.id,
        VendorMembership.state != 'revoked')):
        raise HTTPException(403, 'Independent review required')
    return [document_dict(d) for d in _documents(db, org.id)]


@admin_router.get('/{org_id}/documents/{doc_id}/download')
def admin_download_document(org_id: UUID, doc_id: UUID, admin: User = Depends(require_admin), db: Session = Depends(get_db),
                            _mfa=Depends(require_privileged_mfa)):
    org = db.get(VendorOrganization, org_id)
    if org is None:
        raise HTTPException(404, 'Organization not found')
    # Do not allow a reviewer to download evidence from an organization they own or belong to.
    from tourismo.core.models import VendorMembership
    if org.owner_id == admin.id or db.scalar(select(VendorMembership.id).where(
        VendorMembership.organization_id == org_id, VendorMembership.user_id == admin.id,
        VendorMembership.state != 'revoked')):
        raise HTTPException(403, 'Independent review required')
    return _download(_document(db, org_id, doc_id))
