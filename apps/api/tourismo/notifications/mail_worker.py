"""Resend transactional-email outbox worker.

Run this in ONE independently managed worker service (or --once for an ops probe).
Do not run inside a FastAPI request or duplicate per Uvicorn worker.
"""
import argparse
from datetime import timedelta
from html import escape
import logging
import time
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import httpx
from sqlalchemy import and_, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from tourismo.core.config import get_settings
from tourismo.core.database import get_engine
from tourismo.core.models import (EmailPreference, EmailOutbox, EmailBroadcastJob,
    PlatformAnnouncement, User, UserNotification, now_utc)

logger = logging.getLogger('tourismo.email_worker')
MAX_ATTEMPTS = 5


def validate_configuration():
    settings = get_settings()
    parsed = urlsplit(settings.public_app_origin)
    if (not settings.email_enabled or not settings.resend_api_key or
            not settings.notification_email_from or parsed.scheme != 'https' or
            not parsed.netloc or parsed.username or parsed.password or
            parsed.path not in ('', '/') or parsed.query or parsed.fragment):
        raise ValueError('Email requires EMAIL_ENABLED=true, RESEND_API_KEY, NOTIFICATION_EMAIL_FROM and a public HTTPS PUBLIC_APP_ORIGIN')
    return settings


def fanout_one_batch(db: Session, batch_size: int = 150) -> int:
    """Generate opt-in release email jobs in bounded, restartable transactions."""
    job = db.scalar(select(EmailBroadcastJob).where(EmailBroadcastJob.finished.is_(False))
                    .order_by(EmailBroadcastJob.updated_at).with_for_update(skip_locked=True).limit(1))
    if job is None:
        return 0
    announcement = db.get(PlatformAnnouncement, job.announcement_id)
    now = now_utc()
    if announcement is None or (announcement.expires_at and announcement.expires_at <= now):
        job.finished = True
        db.commit()
        return 0
    stmt = (select(User.id).join(EmailPreference, EmailPreference.user_id == User.id)
            .where(EmailPreference.releases_enabled.is_(True), User.status == 'active',
                   User.email.is_not(None), User.created_at <= announcement.published_at,
                   EmailPreference.updated_at <= announcement.published_at))
    if job.last_user_id is not None:
        stmt = stmt.where(User.id > job.last_user_id)
    ids = db.scalars(stmt.order_by(User.id).limit(batch_size)).all()
    for user_id in ids:
        db.execute(insert(EmailOutbox).values(
            id=uuid4(), recipient_id=user_id, announcement_id=announcement.id,
            idempotency_key=f'release:{announcement.id}:{user_id}', state='queued',
            attempts=0, next_attempt_at=now, created_at=now,
        ).on_conflict_do_nothing(index_elements=['idempotency_key']))
    if ids:
        job.last_user_id = ids[-1]
    if len(ids) < batch_size:
        job.finished = True
    job.updated_at = now
    db.commit()
    return len(ids)


def claim_one(db: Session) -> str | None:
    now = now_utc()
    row = db.scalar(select(EmailOutbox).where(
        or_(and_(EmailOutbox.state == 'queued', EmailOutbox.next_attempt_at <= now),
            and_(EmailOutbox.state == 'sending', EmailOutbox.lease_until < now)))
        .order_by(EmailOutbox.created_at, EmailOutbox.id)
        .with_for_update(skip_locked=True).limit(1))
    if row is None:
        return None
    row.state = 'sending'
    row.lease_until = now + timedelta(minutes=3)
    row.attempts += 1
    item_id = str(row.id)
    db.commit()
    return item_id


def payload_for(db: Session, row: EmailOutbox):
    user = db.get(User, row.recipient_id)
    pref = db.get(EmailPreference, row.recipient_id)
    if user is None or user.status != 'active' or not user.email:
        return None
    if row.notification_id is not None:
        if pref is not None and not pref.activity_enabled:
            return None
        notification = db.get(UserNotification, row.notification_id)
        if notification is None or notification.recipient_id != row.recipient_id:
            return None
        subject, body, link = notification.title, notification.body, notification.target_url
    else:
        if pref is None or not pref.releases_enabled:
            return None
        announcement = db.get(PlatformAnnouncement, row.announcement_id)
        if (announcement is None or announcement.published_at < user.created_at or
                pref.updated_at > announcement.published_at or
                (announcement.expires_at and announcement.expires_at <= now_utc())):
            return None
        subject, body, link = announcement.title, announcement.body, announcement.target_url
    if not link.startswith('/') or link.startswith('//') or '\\' in link:
        return None
    return user.email, subject, body, link


def send_via_resend(settings, to: str, subject: str, body: str, link: str, dedupe: str):
    url = settings.public_app_origin.rstrip('/') + link
    plain = f'{body}\n\nView on Tourismo: {url}\n\nChange your email preferences in Tourismo: {settings.public_app_origin.rstrip("/")}/notifications'
    html = ('<p>' + escape(body).replace('\n', '<br>') + '</p>'
            '<p><a href="' + escape(url, quote=True) + '">View on Tourismo</a></p>'
            '<p><small>Manage email notifications in your Tourismo account.</small></p>')
    response = httpx.post('https://api.resend.com/emails',
        headers={'Authorization': 'Bearer ' + settings.resend_api_key,
                 'Idempotency-Key': dedupe[:190]},
        json={'from': settings.notification_email_from, 'to': [to],
              'subject': subject, 'text': plain, 'html': html}, timeout=12.0)
    response.raise_for_status()
    data = response.json()
    return str(data.get('id', ''))[:120]


def deliver_one(db: Session, item_id: str, settings):
    row = db.get(EmailOutbox, UUID(item_id))
    if row is None or row.state != 'sending':
        return
    now = now_utc()
    if row.created_at < now - timedelta(days=7):
        row.state, row.last_status = 'suppressed', 'expired_notification'
    else:
        data = payload_for(db, row)
        if data is None:
            row.state, row.last_status = 'suppressed', 'no_verified_email_or_opted_out'
        else:
            try:
                provider_id = send_via_resend(settings, *data, row.idempotency_key)
                row.state, row.provider_id, row.sent_at = 'sent', provider_id, now
                row.last_status = 'provider_accepted'
            except httpx.HTTPStatusError as exc:
                code = exc.response.status_code
                permanent = 400 <= code < 500 and code not in (408, 429)
                row.state = 'failed' if permanent or row.attempts >= MAX_ATTEMPTS else 'queued'
                row.last_status = f'provider_http_{code}'
            except (httpx.HTTPError, ValueError, TypeError):
                row.state = 'failed' if row.attempts >= MAX_ATTEMPTS else 'queued'
                row.last_status = 'provider_connection_error'
            if row.state == 'queued':
                row.next_attempt_at = now + timedelta(seconds=min(3600, 45 * 2 ** min(row.attempts, 6)))
    row.lease_until = None
    db.commit()


def run_once(settings, max_events: int = 20) -> tuple[int, int]:
    with Session(get_engine(), expire_on_commit=False) as db:
        fanout_count = fanout_one_batch(db)
        sent = 0
        for _ in range(max_events):
            item = claim_one(db)
            if not item:
                break
            deliver_one(db, item, settings)
            sent += 1
            # Provider API quotas vary; keep throughput intentionally modest.
            time.sleep(0.55)
        return fanout_count, sent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once', action='store_true', help='Process a bounded batch and exit')
    parser.add_argument('--check', action='store_true', help='Validate settings only; no messages sent')
    options = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s %(message)s')
    settings = validate_configuration()
    if options.check:
        logger.info('Email delivery settings are present; DNS/domain and delivery still need external verification')
        return
    while True:
        try:
            queued, processed = run_once(settings)
            logger.info('Processed email batches: release_recipients=%s events=%s', queued, processed)
        except Exception:
            logger.exception('Email worker batch failed; retrying')
            if options.once:
                raise
        if options.once:
            return
        time.sleep(10)


if __name__ == '__main__':
    main()
