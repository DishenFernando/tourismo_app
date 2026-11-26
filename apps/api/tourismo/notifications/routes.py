"""Authenticated notification inbox and manually published release notices.

No email, SMS, browser push, or background worker is implied by these endpoints.
"""
from datetime import timedelta
import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select, update, or_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tourismo.admin.permissions import require_admin
from tourismo.core.database import get_db
from tourismo.core.models import (
    AnnouncementRead, AuditEvent, PlatformAnnouncement, User, UserNotification, now_utc,
)
from tourismo.identity.security import require_privileged_mfa, require_user

router = APIRouter(prefix='/api/v1/notifications', tags=['notifications'])
admin_router = APIRouter(prefix='/api/v1/admin/announcements', tags=['release-announcements'])


class PublishAnnouncement(BaseModel):
    model_config = ConfigDict(extra='forbid')
    release_key: str = Field(min_length=4, max_length=64, pattern=r'^[a-zA-Z0-9][a-zA-Z0-9._-]{3,63}$')
    title: str = Field(min_length=8, max_length=160)
    body: str = Field(min_length=15, max_length=600)
    target_url: str = Field(default='/notifications', max_length=400)
    expires_in_days: int = Field(default=30, ge=1, le=90)

    @field_validator('title', 'body')
    @classmethod
    def clean(cls, value: str) -> str:
        if len(value.strip()) < 8:
            raise ValueError('Text is too short')
        return value.strip()

    @field_validator('target_url')
    @classmethod
    def validate_local_link(cls, url: str) -> str:
        # Only internal, path-only URLs. Do not accept redirects, schemes or fragments.
        if (not url.startswith('/') or url.startswith('//') or '\\' in url
                or '?' in url or '#' in url or '..' in url or any(ord(x) < 32 for x in url)
                or not re.fullmatch(r'/[a-zA-Z0-9/_-]*', url)):
            raise ValueError('Use an internal Tourismo path such as /discover')
        return url


def _announcements(db: Session, user: User):
    now = now_utc()
    return (select(PlatformAnnouncement).where(
        PlatformAnnouncement.published_at <= now,
        PlatformAnnouncement.published_at >= user.created_at,
        or_(PlatformAnnouncement.expires_at.is_(None), PlatformAnnouncement.expires_at > now)))


def _unread_count(db: Session, user: User) -> int:
    personal = db.scalar(select(func.count(UserNotification.id)).where(
        UserNotification.recipient_id == user.id, UserNotification.read_at.is_(None))) or 0
    broadcasts = db.scalar(select(func.count(PlatformAnnouncement.id)).where(
        PlatformAnnouncement.id.in_(
            _announcements(db, user).with_only_columns(PlatformAnnouncement.id)
        ), ~PlatformAnnouncement.id.in_(select(AnnouncementRead.announcement_id).where(
            AnnouncementRead.user_id == user.id)))) or 0
    return int(personal) + int(broadcasts)


def _view(row, read_at=None, announcement=False):
    read = read_at if announcement else row.read_at
    stamp = row.published_at if announcement else row.created_at
    return {'id': str(row.id), 'kind': 'release_update' if announcement else row.kind,
            'title': row.title, 'body': row.body, 'target_url': row.target_url,
            'created_at': stamp.isoformat() if stamp else None,
            'read': read is not None, 'announcement': announcement}


@router.get('')
def my_notifications(limit: int = Query(default=30, ge=1, le=50),
                     offset: int = Query(default=0, ge=0, le=200),
                     user: User = Depends(require_user), db: Session = Depends(get_db)):
    # Bound both queries; sort and merge without downloading all notification history.
    upto = limit + offset + 1
    personal = db.scalars(select(UserNotification).where(UserNotification.recipient_id == user.id)
        .order_by(UserNotification.created_at.desc(), UserNotification.id.desc()).limit(upto)).all()
    announcements = db.scalars(_announcements(db, user).order_by(
        PlatformAnnouncement.published_at.desc(), PlatformAnnouncement.id.desc()).limit(upto)).all()
    receipts = set(db.scalars(select(AnnouncementRead.announcement_id).where(
        AnnouncementRead.user_id == user.id,
        AnnouncementRead.announcement_id.in_([row.id for row in announcements]))).all()) if announcements else set()
    results = [_view(x) for x in personal] + [
        _view(x, True if x.id in receipts else None, announcement=True) for x in announcements]
    results.sort(key=lambda x: (x['created_at'] or '', x['id']), reverse=True)
    return {'items': results[offset:offset+limit], 'unread_count': _unread_count(db, user),
            'has_more': len(results) > offset+limit}


@router.get('/unread-count')
def unread_count(user: User = Depends(require_user), db: Session = Depends(get_db)):
    return {'unread_count': _unread_count(db, user)}


def _mark(db: Session, user: User, item_id: UUID) -> bool:
    row = db.scalar(select(UserNotification).where(
        UserNotification.id == item_id, UserNotification.recipient_id == user.id).with_for_update())
    if row is not None:
        if row.read_at is None:
            row.read_at = now_utc()
        return True
    announcement = db.scalar(_announcements(db, user).where(PlatformAnnouncement.id == item_id))
    if announcement is None:
        return False
    db.execute(insert(AnnouncementRead).values(user_id=user.id, announcement_id=item_id,
        read_at=now_utc()).on_conflict_do_nothing())
    return True


@router.post('/read-all')
def read_all(user: User = Depends(require_user), db: Session = Depends(get_db)):
    db.execute(update(UserNotification).where(
        UserNotification.recipient_id == user.id, UserNotification.read_at.is_(None))
        .values(read_at=now_utc()))
    for row in db.scalars(_announcements(db, user)).all():
        db.execute(insert(AnnouncementRead).values(user_id=user.id, announcement_id=row.id,
                   read_at=now_utc()).on_conflict_do_nothing())
    db.commit()
    return {'unread_count': 0}


@router.post('/{item_id}/read')
def mark_read(item_id: UUID, user: User = Depends(require_user), db: Session = Depends(get_db)):
    if not _mark(db, user, item_id):
        raise HTTPException(404, 'Notification not found')
    db.commit()
    return {'read': True}


@admin_router.post('', status_code=201)
def publish_announcement(body: PublishAnnouncement, admin: User = Depends(require_admin),
                         _mfa=Depends(require_privileged_mfa), db: Session = Depends(get_db)):
    """Explicit release communication step; deployments do not publish automatically."""
    now = now_utc()
    announcement = PlatformAnnouncement(
        release_key=body.release_key, title=body.title, body=body.body,
        target_url=body.target_url, created_by=admin.id,
        published_at=now, expires_at=now + timedelta(days=body.expires_in_days))
    db.add(announcement)
    try:
        db.flush()
        db.add(AuditEvent(actor_id=admin.id, action='platform_announcement_published',
                          object_type='platform_announcement', object_id=announcement.id,
                          reason=body.release_key))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, 'This release key was already announced') from exc
    return {'id': str(announcement.id), 'published': True}


class EmailPreferenceWrite(BaseModel):
    model_config = ConfigDict(extra='forbid')
    activity_enabled: bool = Field(strict=True)
    releases_enabled: bool = Field(strict=True)


@router.get('/email-preferences')
def get_email_preferences(user: User = Depends(require_user), db: Session = Depends(get_db)):
    from tourismo.core.config import get_settings
    from tourismo.core.models import EmailPreference
    row = db.get(EmailPreference, user.id)
    return {
        'activity_enabled': row.activity_enabled if row else True,
        'releases_enabled': row.releases_enabled if row else False,
        'verified_email_available': bool(user.email),
        'delivery_configured': bool(get_settings().email_enabled and get_settings().resend_api_key
                                    and get_settings().notification_email_from and get_settings().public_app_origin),
    }


@router.patch('/email-preferences')
def change_email_preferences(body: EmailPreferenceWrite, user: User = Depends(require_user),
                             db: Session = Depends(get_db)):
    from tourismo.core.models import EmailPreference
    row = db.get(EmailPreference, user.id)
    if row is None:
        row = EmailPreference(user_id=user.id)
        db.add(row)
    row.activity_enabled = body.activity_enabled
    row.releases_enabled = body.releases_enabled
    row.updated_at = now_utc()
    db.commit()
    return get_email_preferences(user, db)
