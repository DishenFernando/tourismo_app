"""Phase 9C: authorization, strict moderation and in-app notification contracts."""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.dialects.postgresql import dialect

from tourismo.core.models import (
    UserNotification, PlatformAnnouncement, AnnouncementRead, CustomerReview,
)
from tourismo.main import app
from tourismo.reviews import routes as reviews
from tourismo.notifications import routes as notices
from tourismo.notifications.service import queue_notification


def test_private_notification_tables_and_unique_dedupe():
    assert UserNotification.__tablename__ == 'user_notifications'
    assert PlatformAnnouncement.__tablename__ == 'platform_announcements'
    assert AnnouncementRead.__tablename__ == 'announcement_reads'
    names = {c.name for c in UserNotification.__table__.constraints if c.name}
    assert 'uq_user_notification_dedupe' in names


def test_idempotent_welcome_write_uses_postgres_conflict_guard():
    db = Mock()
    queue_notification(db, uuid4(), 'welcome', 'Welcome to Tourismo',
                       'Account created.', '/account', 'welcome:v1')
    sql = str(db.execute.call_args.args[0].compile(dialect=dialect()))
    assert 'ON CONFLICT ON CONSTRAINT uq_user_notification_dedupe DO NOTHING' in sql


def test_other_account_cannot_edit_published_review_even_when_id_known(monkeypatch):
    current_user=SimpleNamespace(id=uuid4(),profile_completed_at=datetime.now(timezone.utc))
    foreign_review=SimpleNamespace(id=uuid4(),author_id=uuid4(),state='published')
    db=Mock();db.scalar.return_value=foreign_review
    monkeypatch.setattr(reviews, '_public_listing', lambda *_: pytest.fail('Must not reach listing'))
    with pytest.raises(HTTPException) as exc:
        reviews.edit_feedback(foreign_review.id,reviews.ReviewWrite(
            rating=3,title='Edited by a stranger',
            body='This text should never be saved by the other account.'),current_user,db)
    assert exc.value.status_code==404
    db.commit.assert_not_called()
    query=str(db.scalar.call_args.args[0].compile(dialect=dialect()))
    assert 'customer_reviews.author_id' in query
    assert 'customer_reviews.id' in query


def test_admin_cannot_use_traveler_edit_endpoint(monkeypatch):
    admin=SimpleNamespace(id=uuid4(), profile_completed_at=datetime.now(timezone.utc))
    row=SimpleNamespace(id=uuid4(), author_id=uuid4(), state='published')
    db=Mock();db.scalar.return_value=row
    with pytest.raises(HTTPException) as err:
        reviews.edit_feedback(row.id,reviews.ReviewWrite(
            rating=4,title='Attempted edit',body='An admin should not alter a customer opinion.'),admin,db)
    assert err.value.status_code == 404
    db.commit.assert_not_called()


def test_review_takedown_is_soft_deletion_with_audit_and_author_notification(monkeypatch):
    admin=SimpleNamespace(id=uuid4());author=uuid4()
    review=SimpleNamespace(id=uuid4(), author_id=author, state='published')
    reply=SimpleNamespace(state='published')
    db=Mock();db.scalar.return_value=review;db.get.return_value=reply
    queued=[]
    monkeypatch.setattr(reviews,'queue_notification',lambda *a:queued.append(a))
    res=reviews.remove_violation_review(review.id,reviews.RemovalReason(
        reason='Contains disallowed personal information'),admin,None,db)
    assert res == {'state':'hidden','removed':True}
    assert review.state == 'hidden' and reply.state == 'hidden'
    assert queued and queued[0][1] == author
    assert db.add.called and db.commit.call_count == 1
    db.delete.assert_not_called()


def test_unauthenticated_notification_and_announcement_apis_are_restricted():
    with TestClient(app) as client:
        assert client.get('/api/v1/notifications').status_code == 401
        assert client.get('/api/v1/notifications/unread-count').status_code == 401
        assert client.post('/api/v1/notifications/read-all').status_code == 401
        assert client.post(f'/api/v1/notifications/{uuid4()}/read').status_code == 401
        assert client.post('/api/v1/admin/announcements',json={
            'release_key':'tourismo-2.1.1', 'title':'New release',
            'body':'We improved the travel planning interface.'}).status_code==401
        assert client.post(f'/api/v1/admin/customer-reviews/{uuid4()}/remove',json={
            'reason':'Policy violation in published review'}).status_code == 401


@pytest.mark.parametrize('url',['https://evil.example','//evil.example','/../admin','/plan?next=evil',
                                 '/bad\\path','javascript:alert(1)'])
def test_release_link_rejects_external_and_redirect_urls(url):
    with pytest.raises(ValidationError):
        notices.PublishAnnouncement(release_key='tourismo-2.1.1',title='Travel features',
                                    body='The latest Tourismo update was deployed.',target_url=url)


def test_private_item_read_never_loads_foreign_notification_as_owned():
    user = SimpleNamespace(id=uuid4(),created_at=datetime.now(timezone.utc))
    db=Mock();db.scalar.side_effect=[None,None]
    assert notices._mark(db,user,uuid4()) is False
    db.commit.assert_not_called()
    sql=str(db.scalar.call_args_list[0].args[0].compile(dialect=dialect()))
    assert 'user_notifications.recipient_id' in sql


def test_announcements_are_not_auto_broadcast_on_deploy():
    routes={(route.path,method) for route in app.routes for method in (getattr(route,'methods',set()) or set())}
    assert ('/api/v1/admin/announcements','POST') in routes
    # Creating a release announcement is an explicit admin+MFA action.
    from tourismo.identity.security import require_privileged_mfa
    from tourismo.admin.permissions import require_admin
    dependencies=[d.call for d in next(r for r in app.routes if r.path=='/api/v1/admin/announcements').dependant.dependencies]
    assert require_admin in dependencies
    assert require_privileged_mfa in dependencies
