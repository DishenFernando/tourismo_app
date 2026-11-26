"""Transaction-friendly notification writes, without external transport dependencies.

Call within the parent business transaction; the outer route commits once.
Recipients are resolved server-side, never provided by untrusted clients.
"""
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from tourismo.core.models import UserNotification, VendorMembership, VendorOrganization


def queue_notification(db: Session, recipient_id: UUID, kind: str, title: str,
                       body: str, target_url: str, dedupe_key: str) -> None:
    if not target_url.startswith('/') or target_url.startswith('//') or '\\' in target_url:
        raise ValueError('Notifications must contain local links')
    stmt = insert(UserNotification).values(
        id=uuid4(), recipient_id=recipient_id, kind=kind, title=title[:160],
        body=body[:600], target_url=target_url[:400], dedupe_key=dedupe_key[:190]
    ).on_conflict_do_nothing(constraint='uq_user_notification_dedupe')
    db.execute(stmt)


def business_recipients(db: Session, organization_id: UUID) -> set[UUID]:
    """Notify owner and active managers only, not inactive or pending team members."""
    owner = db.scalar(select(VendorOrganization.owner_id).where(VendorOrganization.id == organization_id))
    manager_ids = db.scalars(select(VendorMembership.user_id).where(
        VendorMembership.organization_id == organization_id,
        VendorMembership.state == 'active', VendorMembership.role == 'manager')).all()
    return ({owner} if owner else set()) | set(manager_ids)


def notify_review_published(db: Session, review_id: UUID, organization_id: UUID,
                            listing_slug: str, listing_title: str) -> None:
    for user_id in business_recipients(db, organization_id):
        queue_notification(db, user_id, 'new_review', 'New customer review',
                           f'A traveler posted a review of {listing_title}.',
                           f'/listings/{listing_slug}', f'review-published:{review_id}')


def notify_enquiry(db: Session, enquiry_id: UUID, organization_id: UUID,
                   listing_title: str, sender_id: UUID) -> None:
    for user_id in business_recipients(db, organization_id) - {sender_id}:
        queue_notification(db, user_id, 'new_enquiry', 'New tourist enquiry',
                           f'A traveler contacted you about {listing_title}.',
                           '/vendor/enquiries', f'enquiry-created:{enquiry_id}')
