"""Manual/externally scheduled vendor compliance and malware-scan maintenance.

Example: docker compose ... exec app python -m tourismo.vendors.operations expire --confirm
No task runs in-process or during page requests. Use a secure scheduler in production.
"""
import argparse
from datetime import date
from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from tourismo.core.database import get_engine
from tourismo.core.models import AuditEvent, VendorDocument, VendorEvidence, VendorOrganization
from tourismo.vendors.documents import scan_with_clamav, private_directory


def expire_licenses(db: Session, today: date | None = None) -> int:
    today = today or date.today()
    rows = db.scalars(select(VendorOrganization).where(VendorOrganization.verification_state == 'approved',
        exists(select(VendorEvidence.id).where(VendorEvidence.organization_id == VendorOrganization.id,
              VendorEvidence.expires_on.is_not(None), VendorEvidence.expires_on < today)))).all()
    for row in rows:
        row.verification_state = 'expired_license'
        row.review_feedback = 'One or more verified evidence references expired; renewal review required.'
        db.add(AuditEvent(actor_id=None, action='vendor.verification.expired_license',
                          object_type='vendor_organization', object_id=row.id,
                          reason='Automated check: evidence expiry date passed'))
    db.commit()
    return len(rows)


def scan_pending(db: Session) -> dict[str, int]:
    root = private_directory()
    results = {'clean': 0, 'infected': 0, 'pending_scan': 0}
    docs = db.scalars(select(VendorDocument).where(VendorDocument.scan_state == 'pending_scan',
                     VendorDocument.deleted_at.is_(None)).limit(100)).all()
    for doc in docs:
        path = root / doc.storage_key
        result = scan_with_clamav(path) if path.is_file() else 'pending_scan'
        if result != 'pending_scan':
            db.add(AuditEvent(actor_id=None, action='vendor.document.scan_' + result,
                              object_type='vendor_organization', object_id=doc.organization_id,
                              reason='Antivirus result for document ' + str(doc.id)))
        doc.scan_state = result
        results[result] += 1
        if result == 'infected':
            path.unlink(missing_ok=True)
    db.commit()
    return results


def main():
    parser = argparse.ArgumentParser(description='Vendor verification maintenance')
    parser.add_argument('action', choices=['expire', 'scan-pending'])
    parser.add_argument('--confirm', action='store_true')
    args = parser.parse_args()
    if not args.confirm:
        parser.error('This command updates compliance status; pass --confirm after reviewing its effect')
    with Session(get_engine()) as db:
        print(expire_licenses(db) if args.action == 'expire' else scan_pending(db))


if __name__ == '__main__':
    main()
