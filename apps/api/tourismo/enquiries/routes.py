"""Phase 8: private, listing-scoped requests for information or quotes (not bookings)."""
from datetime import timedelta
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tourismo.admin.permissions import require_admin
from tourismo.core.database import get_db
from tourismo.core.models import (
    AuditEvent, ServiceEnquiry, ServiceEnquiryMessage, ServiceEnquiryReport,
    ServiceListing, User, now_utc,
)
from tourismo.identity.security import require_privileged_mfa, require_user
from tourismo.listings.routes import _public_query
from tourismo.reviews.routes import _is_affiliated
from tourismo.vendors.routes import _organization
from tourismo.notifications.service import notify_enquiry, business_recipients, queue_notification

traveler_router = APIRouter(prefix='/api/v1/enquiries', tags=['tourist-enquiries'])
vendor_router = APIRouter(prefix='/api/v1/vendor', tags=['vendor-enquiries'])
admin_router = APIRouter(prefix='/api/v1/admin/enquiry-reports', tags=['enquiry-abuse-moderation'])

ReportReason = Literal['spam', 'abuse', 'privacy', 'misleading', 'other']


class NewEnquiry(BaseModel):
    model_config = ConfigDict(extra='forbid')
    subject: str = Field(min_length=8, max_length=140)
    message: str = Field(min_length=20, max_length=2000)

    @field_validator('subject', 'message')
    @classmethod
    def normalize(cls, value: str, info: ValidationInfo) -> str:
        value = value.strip()
        if len(value) < (20 if info.field_name == 'message' else 8):
            raise ValueError('Please describe your enquiry')
        return value


class NewMessage(BaseModel):
    model_config = ConfigDict(extra='forbid')
    body: str = Field(min_length=10, max_length=2000)

    @field_validator('body')
    @classmethod
    def normalize(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 10:
            raise ValueError('A message must be at least 10 characters')
        return value


class NewReport(BaseModel):
    model_config = ConfigDict(extra='forbid')
    reason: ReportReason
    explanation: str = Field(min_length=20, max_length=600)

    @field_validator('explanation')
    @classmethod
    def normalize(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 20:
            raise ValueError('Please explain the concern')
        return value


class ReportDecision(BaseModel):
    model_config = ConfigDict(extra='forbid')
    decision: Literal['dismissed', 'block_thread']
    reason: str = Field(min_length=15, max_length=600)

    @field_validator('reason')
    @classmethod
    def normalize(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 15:
            raise ValueError('Please enter a decision reason')
        return value


def _audit(db: Session, user: User, action: str, item_id: UUID, reason: str | None = None):
    # Do not store private message text or reporter explanations in shared audit events.
    db.add(AuditEvent(actor_id=user.id, action=action, object_type='service_enquiry',
                      object_id=item_id, reason=reason[:300] if reason else None))


def _read_own(db: Session, enquiry_id: UUID, user: User, lock: bool = False) -> ServiceEnquiry:
    query = select(ServiceEnquiry).where(
        ServiceEnquiry.id == enquiry_id, ServiceEnquiry.traveler_id == user.id)
    enquiry = db.scalar(query.with_for_update() if lock else query)
    if enquiry is None:
        raise HTTPException(404, 'Enquiry not found')
    return enquiry


def _read_vendor(db: Session, org_id: UUID, enquiry_id: UUID, user: User,
                 lock: bool = False) -> ServiceEnquiry:
    # Resolve membership from persistent database, never from browser-provided roles.
    _organization(db, org_id, user, roles=('owner', 'manager'))
    query = select(ServiceEnquiry).join(
        ServiceListing, ServiceListing.id == ServiceEnquiry.listing_id).where(
        ServiceEnquiry.id == enquiry_id, ServiceListing.organization_id == org_id)
    enquiry = db.scalar(query.with_for_update(of=ServiceEnquiry) if lock else query)
    if enquiry is None:
        raise HTTPException(404, 'Enquiry not found')
    return enquiry


def _summary(enquiry: ServiceEnquiry, listing: ServiceListing) -> dict:
    return {
        'id': str(enquiry.id), 'listing_slug': listing.slug, 'listing_title': listing.title,
        'subject': enquiry.subject, 'state': enquiry.state,
        'created_at': enquiry.created_at.isoformat() if enquiry.created_at else None,
        'updated_at': enquiry.updated_at.isoformat() if enquiry.updated_at else None,
    }


def _message_view(message: ServiceEnquiryMessage) -> dict:
    # Public-facing API projections deliberately omit user IDs and contact details.
    return {'id': str(message.id), 'sender': message.sender_type,
            'body': message.body, 'created_at': message.created_at.isoformat() if message.created_at else None}


def _thread(db: Session, enquiry: ServiceEnquiry, listing: ServiceListing,
            offset: int, limit: int) -> dict:
    base = select(ServiceEnquiryMessage).where(ServiceEnquiryMessage.enquiry_id == enquiry.id)
    count = db.scalar(select(func.count()).select_from(ServiceEnquiryMessage).where(
        ServiceEnquiryMessage.enquiry_id == enquiry.id)) or 0
    # Reverse to display oldest -> newest among the selected *latest* page of messages.
    messages = list(reversed(db.scalars(base.order_by(
        ServiceEnquiryMessage.created_at.desc(), ServiceEnquiryMessage.id.desc())
        .offset(offset).limit(limit)).all()))
    return {**_summary(enquiry, listing), 'messages': [_message_view(row) for row in messages],
            'has_more': offset + len(messages) < count}


def _allow_reply(enquiry: ServiceEnquiry):
    if enquiry.state not in ('open', 'answered'):
        raise HTTPException(409, 'This enquiry is closed to new messages')


def _add_message(db: Session, enquiry: ServiceEnquiry, user: User,
                 sender: Literal['traveler', 'vendor'], body: str):
    _allow_reply(enquiry)
    since = now_utc() - timedelta(hours=1)
    sent_recently = db.scalar(select(func.count()).select_from(ServiceEnquiryMessage).where(
        ServiceEnquiryMessage.sender_id == user.id, ServiceEnquiryMessage.created_at >= since)) or 0
    if sent_recently >= 40:
        raise HTTPException(429, 'Message limit reached. Try again later')
    row = ServiceEnquiryMessage(enquiry_id=enquiry.id, sender_id=user.id,
                                sender_type=sender, body=body)
    db.add(row)
    enquiry.state = 'answered' if sender == 'vendor' else 'open'
    enquiry.updated_at = now_utc()
    db.flush()
    _audit(db, user, f'enquiry_message_{sender}', enquiry.id)
    if sender == 'vendor':
        queue_notification(db, enquiry.traveler_id, 'enquiry_reply', 'Provider replied to your enquiry',
                           'A business has responded. Open your Tourismo enquiry to read the message.',
                           f'/enquiries?id={enquiry.id}', f'enquiry-message:{row.id}')
    else:
        listing = db.get(ServiceListing, enquiry.listing_id)
        if listing is not None:
            for recipient in business_recipients(db, listing.organization_id) - {user.id}:
                queue_notification(db, recipient, 'enquiry_followup', 'Traveler replied to an enquiry',
                                   f'A traveler replied about {listing.title}.',
                                   '/vendor/enquiries', f'enquiry-message:{row.id}')
    db.commit()
    return {'sent': True, 'state': enquiry.state, 'message': _message_view(row)}


@traveler_router.post('/listings/{slug}', status_code=201)
def create_enquiry(slug: str, body: NewEnquiry, user: User = Depends(require_user),
                   db: Session = Depends(get_db)):
    if user.profile_completed_at is None:
        raise HTTPException(403, 'Complete your Tourismo profile before sending an enquiry')
    listing = db.scalar(_public_query().where(ServiceListing.slug == slug))
    if listing is None:
        raise HTTPException(404, 'Service listing is not publicly available')
    if _is_affiliated(db, user.id, listing.organization_id):
        raise HTTPException(403, 'Business members cannot enquire about their own service')
    since = now_utc() - timedelta(hours=24)
    if (db.scalar(select(func.count()).select_from(ServiceEnquiry).where(
            ServiceEnquiry.traveler_id == user.id, ServiceEnquiry.created_at >= since)) or 0) >= 8:
        raise HTTPException(429, 'Daily enquiry limit reached. Try again tomorrow')
    active = db.scalar(select(ServiceEnquiry.id).where(
        ServiceEnquiry.traveler_id == user.id, ServiceEnquiry.listing_id == listing.id,
        ServiceEnquiry.state.in_(['open', 'answered'])).limit(1))
    if active is not None:
        raise HTTPException(409, 'You already have an active enquiry for this service')
    enquiry = ServiceEnquiry(listing_id=listing.id, traveler_id=user.id, subject=body.subject)
    db.add(enquiry)
    try:
        db.flush()
        db.add(ServiceEnquiryMessage(enquiry_id=enquiry.id, sender_id=user.id,
                                     sender_type='traveler', body=body.message))
        _audit(db, user, 'enquiry_created', enquiry.id)
        notify_enquiry(db, enquiry.id, listing.organization_id, listing.title, user.id)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, 'You already have an active enquiry; refresh your inbox') from exc
    return {'enquiry': _summary(enquiry, listing),
            'message': 'Enquiry sent. This is not a booking or availability confirmation.'}


@traveler_router.get('')
def my_enquiries(limit: int = Query(default=30, ge=1, le=50),
                 offset: int = Query(default=0, ge=0, le=1000),
                 user: User = Depends(require_user), db: Session = Depends(get_db)):
    rows = db.execute(select(ServiceEnquiry, ServiceListing).join(
        ServiceListing, ServiceListing.id == ServiceEnquiry.listing_id).where(
        ServiceEnquiry.traveler_id == user.id).order_by(
        ServiceEnquiry.updated_at.desc(), ServiceEnquiry.id.desc())
        .offset(offset).limit(limit)).all()
    return [_summary(enquiry, listing) for enquiry, listing in rows]


@traveler_router.get('/{enquiry_id}')
def my_enquiry(enquiry_id: UUID, offset: int = Query(default=0, ge=0, le=10000),
               limit: int = Query(default=50, ge=1, le=100),
               user: User = Depends(require_user), db: Session = Depends(get_db)):
    enquiry = _read_own(db, enquiry_id, user)
    return _thread(db, enquiry, db.get(ServiceListing, enquiry.listing_id), offset, limit)


@traveler_router.post('/{enquiry_id}/messages', status_code=201)
def traveler_message(enquiry_id: UUID, body: NewMessage,
                     user: User = Depends(require_user), db: Session = Depends(get_db)):
    enquiry = _read_own(db, enquiry_id, user, lock=True)
    return _add_message(db, enquiry, user, 'traveler', body.body)


@traveler_router.post('/{enquiry_id}/withdraw')
def withdraw_enquiry(enquiry_id: UUID, user: User = Depends(require_user),
                     db: Session = Depends(get_db)):
    enquiry = _read_own(db, enquiry_id, user, lock=True)
    _allow_reply(enquiry)
    enquiry.state, enquiry.updated_at = 'withdrawn', now_utc()
    _audit(db, user, 'enquiry_withdrawn', enquiry.id)
    db.commit()
    return {'state': enquiry.state}


@vendor_router.get('/organizations/{org_id}/enquiries')
def vendor_enquiries(org_id: UUID, limit: int = Query(default=30, ge=1, le=50),
                    offset: int = Query(default=0, ge=0, le=1000),
                    user: User = Depends(require_user), db: Session = Depends(get_db)):
    _organization(db, org_id, user, roles=('owner', 'manager'))
    rows = db.execute(select(ServiceEnquiry, ServiceListing).join(
        ServiceListing, ServiceListing.id == ServiceEnquiry.listing_id).where(
        ServiceListing.organization_id == org_id).order_by(
        ServiceEnquiry.updated_at.desc(), ServiceEnquiry.id.desc())
        .offset(offset).limit(limit)).all()
    return [_summary(enquiry, listing) for enquiry, listing in rows]


@vendor_router.get('/organizations/{org_id}/enquiries/{enquiry_id}')
def vendor_enquiry(org_id: UUID, enquiry_id: UUID,
                   offset: int = Query(default=0, ge=0, le=10000),
                   limit: int = Query(default=50, ge=1, le=100),
                   user: User = Depends(require_user), db: Session = Depends(get_db)):
    enquiry = _read_vendor(db, org_id, enquiry_id, user)
    return _thread(db, enquiry, db.get(ServiceListing, enquiry.listing_id), offset, limit)


@vendor_router.post('/organizations/{org_id}/enquiries/{enquiry_id}/messages', status_code=201)
def vendor_message(org_id: UUID, enquiry_id: UUID, body: NewMessage,
                   user: User = Depends(require_user), db: Session = Depends(get_db)):
    enquiry = _read_vendor(db, org_id, enquiry_id, user, lock=True)
    listing = db.scalar(_public_query().where(ServiceListing.id == enquiry.listing_id))
    if listing is None:
        raise HTTPException(409, 'This listing is no longer public; messaging is disabled')
    return _add_message(db, enquiry, user, 'vendor', body.body)


@vendor_router.post('/organizations/{org_id}/enquiries/{enquiry_id}/close')
def vendor_close(org_id: UUID, enquiry_id: UUID,
                 user: User = Depends(require_user), db: Session = Depends(get_db)):
    enquiry = _read_vendor(db, org_id, enquiry_id, user, lock=True)
    _allow_reply(enquiry)
    enquiry.state, enquiry.updated_at = 'closed', now_utc()
    _audit(db, user, 'enquiry_closed_by_vendor', enquiry.id)
    db.commit()
    return {'state': enquiry.state}


@traveler_router.post('/{enquiry_id}/reports', status_code=201)
def report_enquiry(enquiry_id: UUID, body: NewReport,
                   user: User = Depends(require_user), db: Session = Depends(get_db)):
    # Both the traveler and an active owner/manager may report a conversation.
    enquiry = db.get(ServiceEnquiry, enquiry_id)
    if enquiry is None:
        raise HTTPException(404, 'Enquiry not found')
    listing = db.get(ServiceListing, enquiry.listing_id)
    if user.id != enquiry.traveler_id:
        _organization(db, listing.organization_id, user, roles=('owner', 'manager'))
    report = ServiceEnquiryReport(enquiry_id=enquiry.id, reporter_id=user.id,
                                  reason=body.reason, explanation=body.explanation)
    db.add(report)
    try:
        db.flush()
        _audit(db, user, 'enquiry_reported', enquiry.id, body.reason)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, 'You have already reported this enquiry') from exc
    return {'reported': True, 'message': 'Report sent to Tourismo administrators'}


@admin_router.get('')
def report_queue(state: Literal['open', 'dismissed', 'actioned'] = 'open',
                 limit: int = Query(default=30, ge=1, le=50),
                 admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.execute(select(ServiceEnquiryReport, ServiceEnquiry, ServiceListing)
        .join(ServiceEnquiry, ServiceEnquiry.id == ServiceEnquiryReport.enquiry_id)
        .join(ServiceListing, ServiceListing.id == ServiceEnquiry.listing_id)
        .where(ServiceEnquiryReport.state == state)
        .order_by(ServiceEnquiryReport.created_at.asc()).limit(limit)).all()
    return [{'id': str(report.id), 'enquiry_id': str(enquiry.id),
             'listing_title': listing.title, 'subject': enquiry.subject,
             'reason': report.reason, 'explanation': report.explanation,
             'state': report.state, 'thread_state': enquiry.state}
            for report, enquiry, listing in rows]


@admin_router.post('/{report_id}/decision')
def moderate_report(report_id: UUID, body: ReportDecision,
                    admin: User = Depends(require_admin),
                    _mfa=Depends(require_privileged_mfa), db: Session = Depends(get_db)):
    report = db.scalar(select(ServiceEnquiryReport).where(
        ServiceEnquiryReport.id == report_id).with_for_update())
    if report is None:
        raise HTTPException(404, 'Report not found')
    if report.state != 'open':
        raise HTTPException(409, 'Report already resolved')
    enquiry = db.scalar(select(ServiceEnquiry).where(
        ServiceEnquiry.id == report.enquiry_id).with_for_update())
    if body.decision == 'block_thread':
        enquiry.state = 'blocked'
        enquiry.updated_at = now_utc()
    report.state = 'actioned' if body.decision == 'block_thread' else 'dismissed'
    report.reviewed_by, report.reviewed_at = admin.id, now_utc()
    _audit(db, admin, 'enquiry_report_' + body.decision, enquiry.id,
           body.reason)
    db.commit()
    return {'state': report.state, 'thread_state': enquiry.state}


@admin_router.get('/{report_id}/thread')
def report_thread(report_id: UUID, offset: int = Query(default=0, ge=0, le=10000),
                  admin: User = Depends(require_admin),
                  _mfa=Depends(require_privileged_mfa), db: Session = Depends(get_db)):
    """Sensitive message evidence, restricted to a qualified administrator."""
    report = db.get(ServiceEnquiryReport, report_id)
    if report is None:
        raise HTTPException(404, 'Report not found')
    enquiry = db.get(ServiceEnquiry, report.enquiry_id)
    if enquiry is None:
        raise HTTPException(404, 'Enquiry not found')
    return _thread(db, enquiry, db.get(ServiceListing, enquiry.listing_id), offset, 50)
