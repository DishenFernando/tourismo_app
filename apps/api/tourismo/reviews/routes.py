"""Phase 7: moderated traveler feedback; not a proof of a paid booking or verified visit."""
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tourismo.admin.permissions import require_admin
from tourismo.core.database import get_db
from tourismo.core.models import (
    AuditEvent, CustomerReview, CustomerReviewReply, CustomerReviewReport, CustomerReviewImage,
    ServiceListing, User, VendorMembership, VendorOrganization, now_utc,
)
from tourismo.identity.security import require_privileged_mfa, require_user
from tourismo.listings.routes import _public_query
from tourismo.vendors.routes import _organization
from tourismo.notifications.service import notify_review_published, queue_notification

public_router = APIRouter(prefix='/api/v1/reviews', tags=['traveler-feedback'])
vendor_router = APIRouter(prefix='/api/v1/vendor', tags=['provider-feedback'])
admin_router = APIRouter(prefix='/api/v1/admin/customer-reviews', tags=['customer-review-moderation'])

ReviewState = Literal['pending', 'published', 'changes_requested', 'hidden']
ReportReason = Literal['spam', 'abuse', 'privacy', 'misleading', 'other']


class ReviewWrite(BaseModel):
    model_config = ConfigDict(extra='forbid')
    rating: int = Field(ge=1, le=5, strict=True)
    title: str = Field(min_length=4, max_length=120)
    body: str = Field(min_length=30, max_length=2000)
    images: list[str] | None = Field(default=None, max_length=5)

    @field_validator('title', 'body')
    @classmethod
    def clean(cls, value: str, info: ValidationInfo) -> str:
        cleaned = value.strip()
        minimum = 4 if info.field_name == 'title' else 30
        if len(cleaned) < minimum:
            raise ValueError('Please provide meaningful content')
        return cleaned


class ReplyWrite(BaseModel):
    model_config = ConfigDict(extra='forbid')
    body: str = Field(min_length=20, max_length=1500)

    @field_validator('body')
    @classmethod
    def clean(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 20:
            raise ValueError('A response must contain at least 20 characters')
        return cleaned


class ReportWrite(BaseModel):
    model_config = ConfigDict(extra='forbid')
    reason: ReportReason
    explanation: str = Field(min_length=20, max_length=600)

    @field_validator('explanation')
    @classmethod
    def clean(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 20:
            raise ValueError('A report explanation must contain at least 20 characters')
        return cleaned


class DecisionWrite(BaseModel):
    model_config = ConfigDict(extra='forbid')
    decision: Literal['published', 'changes_requested', 'hidden']
    reason: str = Field(min_length=15, max_length=600)

    @field_validator('reason')
    @classmethod
    def clean(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 15:
            raise ValueError('A moderation reason must contain at least 15 characters')
        return cleaned


class ReportDecision(BaseModel):
    model_config = ConfigDict(extra='forbid')
    decision: Literal['dismissed', 'hide_review']
    reason: str = Field(min_length=15, max_length=600)

    @field_validator('reason')
    @classmethod
    def clean(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 15:
            raise ValueError('A report decision reason must contain at least 15 characters')
        return cleaned


def _public_listing(db: Session, slug: str) -> ServiceListing:
    listing = db.scalar(_public_query().where(ServiceListing.slug == slug))
    if listing is None:
        raise HTTPException(404, 'Service listing is not publicly available')
    return listing


def _review_dict(row: CustomerReview, reply: CustomerReviewReply | None = None,
                 images: list[str] | None = None) -> dict:
    """Only non-identifying, publicly approved content reaches guests."""
    return {'id': str(row.id), 'rating': row.rating, 'title': row.title, 'body': row.body,
            'author_label': 'Tourismo traveler', 'visit_verified': False,
            'created_at': row.created_at.isoformat() if row.created_at else None,
            'images': images or [],
            'response': ({'body': reply.body, 'responded_at': reply.updated_at.isoformat()
                          if reply.updated_at else None} if reply and reply.state == 'published' else None)}


def _own_dict(row: CustomerReview, images: list[str] | None = None) -> dict:
    return {'id': str(row.id), 'rating': row.rating, 'title': row.title, 'body': row.body,
            'state': row.state, 'moderation_note': row.moderation_note, 'images': images or []}


def _audited(db: Session, actor: User, action: str, object_id: UUID, reason: str | None = None):
    db.add(AuditEvent(actor_id=actor.id, action=action, object_type='customer_review',
                      object_id=object_id, reason=reason[:300] if reason else None))


def _is_affiliated(db: Session, user_id: UUID, org_id: UUID) -> bool:
    """Block owners and any active/pending business members from reviewing their own business."""
    owner = db.scalar(select(VendorOrganization.owner_id).where(VendorOrganization.id == org_id))
    if owner == user_id:
        return True
    return db.scalar(select(VendorMembership.id).where(
        VendorMembership.organization_id == org_id, VendorMembership.user_id == user_id,
        VendorMembership.state.in_(['active', 'pending'])).limit(1)) is not None


def _eligible_author(db: Session, user: User, listing: ServiceListing):
    if user.profile_completed_at is None:
        raise HTTPException(403, 'Complete your Tourismo profile before reviewing a service')
    if _is_affiliated(db, user.id, listing.organization_id):
        raise HTTPException(403, 'Business owners and affiliated members cannot review their own services')


@public_router.get('/listings/{slug}')
def listing_feedback(slug: str, limit: int = Query(default=5, ge=1, le=5),
                     offset: int = Query(default=0, ge=0, le=10000), db: Session = Depends(get_db)):
    listing = _public_listing(db, slug)
    base = select(CustomerReview).where(CustomerReview.listing_id == listing.id,
                                        CustomerReview.state == 'published')
    # Count review entries, but average *per reviewer* so five submissions do not
    # give one person's opinion five times the weight of another person's.
    per_author = (select(func.avg(CustomerReview.rating).label('user_average'))
                  .where(CustomerReview.listing_id == listing.id,
                         CustomerReview.state == 'published')
                  .group_by(CustomerReview.author_id).subquery())
    count = db.scalar(select(func.count(CustomerReview.id)).where(
        CustomerReview.listing_id == listing.id,
        CustomerReview.state == 'published')) or 0
    rating = db.scalar(select(func.avg(per_author.c.user_average)))
    rows = db.scalars(base.order_by(CustomerReview.created_at.desc(), CustomerReview.id.desc())
                      .offset(offset).limit(limit)).all()
    replies = {}
    if rows:
        replies = {r.review_id: r for r in db.scalars(select(CustomerReviewReply).where(
            CustomerReviewReply.review_id.in_([row.id for row in rows]),
            CustomerReviewReply.state == 'published')).all()}
    photos = _image_links(db, [r.id for r in rows])
    return {'listing_slug': slug, 'count': int(count),
            'average_rating': round(float(rating), 2) if rating is not None else None,
            'visit_verified': False,
            'reviews': [_review_dict(row, replies.get(row.id), photos.get(row.id, [])) for row in rows]}


@public_router.get('/listings/{slug}/mine')
def my_feedback(slug: str, user: User = Depends(require_user), db: Session = Depends(get_db)):
    listing = _public_listing(db, slug)
    rows = db.scalars(select(CustomerReview).where(
        CustomerReview.listing_id == listing.id, CustomerReview.author_id == user.id)
        .order_by(CustomerReview.created_at.desc(), CustomerReview.id.desc()).limit(5)).all()
    photos = _image_links(db, [row.id for row in rows])
    my_reviews = [_own_dict(row, photos.get(row.id, [])) for row in rows]
    return {'reviews': my_reviews, 'review': my_reviews[0] if my_reviews else None,
            'remaining': max(0, 5 - len(my_reviews))}


@public_router.post('/listings/{slug}', status_code=201)
def submit_feedback(slug: str, body: ReviewWrite, user: User = Depends(require_user),
                    db: Session = Depends(get_db)):
    listing = _public_listing(db, slug)
    _eligible_author(db, user, listing)
    # Serialize concurrent submissions by the same identity. Counting without
    # a row lock is race-prone and could allow more than five reviews.
    locked = db.scalar(select(User.id).where(User.id == user.id).with_for_update())
    if locked is None:
        raise HTTPException(401, 'User session not found')
    count = db.scalar(select(func.count(CustomerReview.id)).where(
        CustomerReview.listing_id == listing.id, CustomerReview.author_id == user.id)) or 0
    if count >= 5:
        raise HTTPException(409, 'You have reached the limit of five reviews for this service')
    row = CustomerReview(listing_id=listing.id, author_id=user.id)
    try:
        return _save_review(db, row, body, user, editing=False)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, 'The review could not be saved; please refresh') from exc


@public_router.post('/{review_id}/reports', status_code=201)
def report_feedback(review_id: UUID, body: ReportWrite, user: User = Depends(require_user),
                    db: Session = Depends(get_db)):
    row = db.get(CustomerReview, review_id)
    if row is None or row.state != 'published':
        raise HTTPException(404, 'Review not found')
    if user.id == row.author_id:
        raise HTTPException(403, 'You cannot report your own review')
    listing = db.get(ServiceListing, row.listing_id)
    if listing is None:
        raise HTTPException(404, 'Review not found')
    _public_listing(db, listing.slug)
    report = CustomerReviewReport(review_id=row.id, reporter_id=user.id,
                                  reason=body.reason, explanation=body.explanation, state='open')
    db.add(report)
    try:
        db.flush()
        _audited(db, user, 'customer_review_reported', row.id, body.reason)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, 'You already reported this review') from exc
    return {'reported': True, 'message': 'Report sent to Tourismo moderation'}


@vendor_router.get('/organizations/{org_id}/customer-reviews')
def provider_reviews(org_id: UUID, user: User = Depends(require_user), db: Session = Depends(get_db)):
    org = _organization(db, org_id, user)
    rows = db.execute(select(CustomerReview, ServiceListing)
        .join(ServiceListing, ServiceListing.id == CustomerReview.listing_id)
        .where(ServiceListing.organization_id == org.id,
               CustomerReview.state == 'published')
        .order_by(CustomerReview.created_at.desc()).limit(100)).all()
    reply_ids = [r.id for r, _ in rows]
    replies = {r.review_id: r for r in db.scalars(select(CustomerReviewReply).where(
        CustomerReviewReply.review_id.in_(reply_ids))).all()} if reply_ids else {}
    photos = _image_links(db, reply_ids)
    return [{'review': _review_dict(r, replies.get(r.id), photos.get(r.id, [])),
             'listing_title': listing.title, 'listing_slug': listing.slug,
             'response_draft': ({'body': replies[r.id].body, 'state': replies[r.id].state,
                                 'moderation_note': replies[r.id].moderation_note}
                                if r.id in replies else None)} for r, listing in rows]


@vendor_router.post('/organizations/{org_id}/customer-reviews/{review_id}/response')
def provider_response(org_id: UUID, review_id: UUID, body: ReplyWrite,
                      user: User = Depends(require_user), db: Session = Depends(get_db)):
    org = _organization(db, org_id, user, ('owner', 'manager'))
    row = db.get(CustomerReview, review_id)
    if row is None or row.state != 'published':
        raise HTTPException(404, 'Published review not found')
    listing = db.get(ServiceListing, row.listing_id)
    if listing is None or listing.organization_id != org.id:
        raise HTTPException(404, 'Published review not found')
    if org.verification_state in ('rejected', 'expired_license'):
        raise HTTPException(409, 'Business is not eligible to respond publicly')
    _public_listing(db, listing.slug)
    reply = db.get(CustomerReviewReply, row.id, with_for_update=True)
    if reply is None:
        reply = CustomerReviewReply(review_id=row.id, organization_id=org.id, author_id=user.id)
        db.add(reply)
    reply.body, reply.author_id, reply.state = body.body, user.id, 'pending'
    reply.moderation_note, reply.moderated_by, reply.moderated_at = None, None, None
    reply.updated_at = now_utc()
    try:
        db.flush()
        _audited(db, user, 'customer_review_provider_reply_submitted', row.id)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, 'A response already exists; refresh and edit it') from exc
    return {'state': reply.state, 'message': 'Provider response submitted for moderation'}


def _review_admin_dict(row: CustomerReview, listing: ServiceListing | None = None) -> dict:
    return {**_own_dict(row), 'listing_id': str(row.listing_id),
            'listing_title': listing.title if listing else None,
            'listing_slug': listing.slug if listing else None,
            'created_at': row.created_at.isoformat() if row.created_at else None}


@admin_router.get('')
def review_queue(state: ReviewState = 'pending', user: User = Depends(require_admin),
                 db: Session = Depends(get_db)):
    rows = db.execute(select(CustomerReview, ServiceListing)
        .join(ServiceListing, ServiceListing.id == CustomerReview.listing_id)
        .where(CustomerReview.state == state)
        .order_by(CustomerReview.created_at.desc() if state == 'published'
                  else CustomerReview.created_at.asc()).limit(100)).all()
    return [_review_admin_dict(row, listing) for row, listing in rows]


@admin_router.post('/{review_id}/decision')
def decide_review(review_id: UUID, body: DecisionWrite,
                  user: User = Depends(require_admin),
                  _mfa=Depends(require_privileged_mfa), db: Session = Depends(get_db)):
    row = db.scalar(select(CustomerReview).where(CustomerReview.id == review_id).with_for_update())
    if row is None:
        raise HTTPException(404, 'Review not found')
    if row.author_id == user.id:
        raise HTTPException(403, 'Moderators cannot approve their own reviews')
    if body.decision == 'published':
        listing = db.get(ServiceListing, row.listing_id)
        if listing is None:
            raise HTTPException(404, 'Listing not found')
        _public_listing(db, listing.slug)
    was_published = row.state == 'published'
    row.state, row.moderation_note = body.decision, body.reason
    row.moderated_by, row.moderated_at = user.id, now_utc()
    if body.decision == 'published' and not was_published:
        listing = db.get(ServiceListing, row.listing_id)
        if listing is not None:
            notify_review_published(db, row.id, listing.organization_id, listing.slug, listing.title)
    elif body.decision == 'hidden' and was_published:
        queue_notification(db, row.author_id, 'review_removed', 'Review removed from public view',
                           'A Tourismo moderator removed one of your reviews following a policy investigation.',
                           '/notifications', f'review-removed:{row.id}')
    if body.decision != 'published':
        reply = db.get(CustomerReviewReply, row.id)
        if reply is not None and reply.state == 'published':
            reply.state = 'hidden'
    _audited(db, user, 'customer_review_moderated', row.id, body.decision + ': ' + body.reason)
    db.commit()
    return {'state': row.state}


@admin_router.get('/replies')
def reply_queue(state: ReviewState = 'pending', user: User = Depends(require_admin),
                db: Session = Depends(get_db)):
    rows = db.execute(select(CustomerReviewReply, CustomerReview, ServiceListing)
        .join(CustomerReview, CustomerReview.id == CustomerReviewReply.review_id)
        .join(ServiceListing, ServiceListing.id == CustomerReview.listing_id)
        .where(CustomerReviewReply.state == state)
        .order_by(CustomerReviewReply.created_at.asc()).limit(100)).all()
    return [{'review_id': str(reply.review_id), 'body': reply.body, 'state': reply.state,
             'moderation_note': reply.moderation_note, 'listing_title': listing.title,
             'review_title': review.title, 'review_state': review.state}
            for reply, review, listing in rows]


@admin_router.post('/replies/{review_id}/decision')
def decide_reply(review_id: UUID, body: DecisionWrite,
                 user: User = Depends(require_admin),
                 _mfa=Depends(require_privileged_mfa), db: Session = Depends(get_db)):
    reply = db.get(CustomerReviewReply, review_id, with_for_update=True)
    if reply is None:
        raise HTTPException(404, 'Provider reply not found')
    if reply.author_id == user.id:
        raise HTTPException(403, 'Moderators cannot approve their own business responses')
    review = db.get(CustomerReview, review_id)
    if body.decision == 'published':
        if review is None or review.state != 'published':
            raise HTTPException(409, 'Customer review must be published first')
        listing = db.get(ServiceListing, review.listing_id)
        if listing is None:
            raise HTTPException(404, 'Listing not found')
        _public_listing(db, listing.slug)
    prior_state = reply.state
    reply.state, reply.moderation_note = body.decision, body.reason
    reply.moderated_by, reply.moderated_at = user.id, now_utc()
    if body.decision == 'published' and prior_state != 'published' and review is not None:
        listing = db.get(ServiceListing, review.listing_id)
        if listing is not None:
            queue_notification(db, review.author_id, 'provider_reply', 'Business replied to your review',
                               f'The provider responded to your review of {listing.title}.',
                               f'/listings/{listing.slug}', f'review-reply:{review.id}')
    _audited(db, user, 'customer_review_provider_reply_moderated', review_id,
             body.decision + ': ' + body.reason)
    db.commit()
    return {'state': reply.state}


@admin_router.get('/reports')
def report_queue(state: Literal['open', 'dismissed', 'actioned'] = 'open',
                 user: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.execute(select(CustomerReviewReport, CustomerReview, ServiceListing)
        .join(CustomerReview, CustomerReview.id == CustomerReviewReport.review_id)
        .join(ServiceListing, ServiceListing.id == CustomerReview.listing_id)
        .where(CustomerReviewReport.state == state)
        .order_by(CustomerReviewReport.created_at.asc()).limit(100)).all()
    return [{'id': str(report.id), 'review_id': str(review.id),
             'reason': report.reason, 'explanation': report.explanation, 'state': report.state,
             'review_title': review.title, 'review_state': review.state,
             'listing_title': listing.title} for report, review, listing in rows]


@admin_router.post('/reports/{report_id}/decision')
def decide_report(report_id: UUID, body: ReportDecision,
                  user: User = Depends(require_admin),
                  _mfa=Depends(require_privileged_mfa), db: Session = Depends(get_db)):
    report = db.scalar(select(CustomerReviewReport).where(CustomerReviewReport.id == report_id).with_for_update())
    if report is None:
        raise HTTPException(404, 'Report not found')
    if report.state != 'open':
        raise HTTPException(409, 'This report has already been decided')
    review = db.scalar(select(CustomerReview).where(CustomerReview.id == report.review_id).with_for_update())
    if review is None:
        raise HTTPException(404, 'Reported review not found')
    if body.decision == 'hide_review':
        review.state = 'hidden'
        review.moderated_by, review.moderated_at = user.id, now_utc()
        review.moderation_note = body.reason
        queue_notification(db, review.author_id, 'review_removed', 'Review removed from public view',
                           'A reported review was removed from public view following a policy decision.',
                           '/notifications', f'review-removed:{review.id}')
        reply = db.get(CustomerReviewReply, review.id)
        if reply is not None:
            reply.state = 'hidden'
        report.state = 'actioned'
    else:
        report.state = 'dismissed'
    report.reviewed_by, report.reviewed_at = user.id, now_utc()
    _audited(db, user, 'customer_review_report_decided', review.id,
             body.decision + ': ' + body.reason)
    db.commit()
    return {'state': report.state}



def _image_links(db: Session, ids: list[UUID]) -> dict[UUID, list[str]]:
    if not ids:
        return {}
    result: dict[UUID, list[str]] = {}
    for image_id, review_id in db.execute(select(CustomerReviewImage.id, CustomerReviewImage.review_id)
            .where(CustomerReviewImage.review_id.in_(ids)).order_by(CustomerReviewImage.position)).all():
        result.setdefault(review_id, []).append('/api/v1/reviews/images/' + str(image_id))
    return result


def _save_review(db: Session, row: CustomerReview, payload: ReviewWrite, user: User, *, editing: bool):
    from tourismo.reviews.safety import moderate_content, normalize_images
    new_images = normalize_images(payload.images)
    previous = []
    if editing and payload.images is None:
        previous = [img.jpeg_data for img in db.scalars(select(CustomerReviewImage)
                    .where(CustomerReviewImage.review_id == row.id)
                    .order_by(CustomerReviewImage.position)).all()]
    state = moderate_content(payload.title, payload.body, new_images if payload.images is not None else previous)
    row.rating, row.title, row.body = payload.rating, payload.title, payload.body
    row.state = state
    row.updated_at = now_utc()
    row.moderation_note, row.moderated_by, row.moderated_at = None, None, None
    db.add(row)
    db.flush()
    if payload.images is not None:
        for img in db.scalars(select(CustomerReviewImage).where(
                CustomerReviewImage.review_id == row.id)).all():
            db.delete(img)
        db.flush()  # release unique (review_id, position) before replacement
        for pos, data in enumerate(new_images):
            db.add(CustomerReviewImage(review_id=row.id, position=pos, jpeg_data=data))
    if editing:
        reply = db.get(CustomerReviewReply, row.id)
        if reply is not None and reply.state == 'published':
            reply.state = 'pending'  # existing Phase 7 behavior
    _audited(db, user, 'customer_review_edited' if editing else 'customer_review_submitted', row.id)
    # New publicly visible reviews notify eligible provider managers after safety clearance.
    # The notification belongs to the same transaction as the review.
    if state == 'published' and not editing:
        listing = db.get(ServiceListing, row.listing_id)
        if listing is not None:
            notify_review_published(db, row.id, listing.organization_id, listing.slug, listing.title)
    db.commit()
    return {'review': _own_dict(row, _image_links(db, [row.id]).get(row.id, [])),
            'message': ('Your review is now public' if state == 'published'
                        else 'Your review is awaiting a safety check by the Tourismo team')}


@public_router.patch('/{review_id}')
def edit_feedback(review_id: UUID, body: ReviewWrite, user: User = Depends(require_user),
                  db: Session = Depends(get_db)):
    # Database-level ownership filter; knowing another review UUID grants no write access.
    row = db.scalar(select(CustomerReview).where(
        CustomerReview.id == review_id, CustomerReview.author_id == user.id).with_for_update())
    if row is None or row.author_id != user.id:
        raise HTTPException(404, 'Your review was not found')
    if row.state == 'hidden':
        raise HTTPException(409, 'This review has been closed by moderation')
    listing = db.get(ServiceListing, row.listing_id)
    if listing is None:
        raise HTTPException(404, 'Service no longer exists')
    _public_listing(db, listing.slug)
    _eligible_author(db, user, listing)
    return _save_review(db, row, body, user, editing=True)


@public_router.get('/images/{image_id}')
def public_review_image(image_id: UUID, db: Session = Depends(get_db)):
    image = db.get(CustomerReviewImage, image_id)
    if image is None:
        raise HTTPException(404, 'Image not found')
    row = db.get(CustomerReview, image.review_id)
    if row is None or row.state != 'published':
        raise HTTPException(404, 'Image not found')
    listing = db.get(ServiceListing, row.listing_id)
    if listing is None:
        raise HTTPException(404, 'Image not found')
    _public_listing(db, listing.slug)
    return Response(content=image.jpeg_data, media_type='image/jpeg', headers={
        'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
    })


class RemovalReason(BaseModel):
    model_config = ConfigDict(extra='forbid')
    reason: str = Field(min_length=15, max_length=600)


@admin_router.post('/{review_id}/remove')
def remove_violation_review(review_id: UUID, body: RemovalReason,
                            admin: User = Depends(require_admin),
                            _mfa=Depends(require_privileged_mfa), db: Session = Depends(get_db)):
    """Immediately remove from every public surface; retain audit/evidence for appeal.

    Destructive hard deletion is NOT exposed. Existing 'hidden' state is a
    tombstone preventing authors from republishing the removed review.
    """
    review = db.scalar(select(CustomerReview).where(CustomerReview.id == review_id).with_for_update())
    if review is None:
        raise HTTPException(404, 'Review not found')
    if review.state == 'hidden':
        raise HTTPException(409, 'Review already removed')
    if review.author_id == admin.id:
        raise HTTPException(403, 'Moderators cannot remove their own reviews')
    review.state = 'hidden'
    review.moderation_note = body.reason.strip()
    review.moderated_by, review.moderated_at = admin.id, now_utc()
    reply = db.get(CustomerReviewReply, review.id)
    if reply is not None:
        reply.state = 'hidden'
    _audited(db, admin, 'customer_review_removed_for_violation', review.id,
             review.moderation_note)
    queue_notification(db, review.author_id, 'review_removed', 'Review removed from public view',
                       'A moderator removed your review for a content-policy concern. Contact support to appeal.',
                       '/notifications', f'review-removed:{review.id}')
    db.commit()
    return {'state': 'hidden', 'removed': True}
