"""Phase 10B regression: no invented route times, consent-gated mail, model integrity."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from tourismo.navigation import routes as navigation
from tourismo.core.models import EmailOutbox, EmailPreference, EmailBroadcastJob
from tourismo.notifications import mail_worker
from tourismo.notifications.routes import EmailPreferenceWrite


def test_great_circle_distance_is_not_road_distance():
    assert navigation.straight_line_km(6.9271, 79.8612, 6.9271, 79.8612) == pytest.approx(0)
    assert 93 < navigation.straight_line_km(6.9271, 79.8612, 7.2906, 80.6337) < 96


@pytest.mark.parametrize('lat,lon', [(91,80), (7,181), (float('inf'),81), (float('nan'),81)])
def test_invalid_location_rejected(lat,lon):
    with pytest.raises(ValidationError):
        navigation.RouteRequest(kind='service',slug='test-hotel',origin_latitude=lat,origin_longitude=lon,mode='driving')


def test_no_route_key_never_generates_fictional_travel_time(monkeypatch):
    target = navigation.Point(kind='destination',slug='kandy',title='Kandy',latitude=7.29,
        longitude=80.63,accuracy_note='Reference',source_url=None)
    monkeypatch.setattr(navigation,'get_target',lambda *_:target)
    monkeypatch.setattr(navigation,'get_settings',lambda:SimpleNamespace(google_routes_api_key=''))
    reply = navigation.estimate(navigation.RouteRequest(kind='destination',slug='kandy',
        origin_latitude=6.9271,origin_longitude=79.8612,mode='transit'),
        Mock(headers={}),object())
    assert reply['road_distance_km'] is None
    assert reply['estimated_minutes'] is None
    assert reply['estimate_status'] == 'provider_not_configured'
    assert reply['straight_line_km'] > 0


def test_missing_listings_do_not_allow_guessing_location(monkeypatch):
    db = Mock()
    db.scalar.return_value = None
    with pytest.raises(HTTPException) as exc:
        navigation.get_target(db, 'service', 'non-existent')
    assert exc.value.status_code == 404


def test_email_preferences_are_strict():
    with pytest.raises(ValidationError):
        EmailPreferenceWrite(activity_enabled='yes',releases_enabled=False)
    assert EmailPreference.__tablename__=='email_preferences'
    assert EmailOutbox.__tablename__=='email_outbox'
    assert EmailBroadcastJob.__tablename__=='email_broadcast_jobs'
    outbox_constraints={c.name for c in EmailOutbox.__table__.constraints if c.name}
    assert 'ck_email_outbox_one_source' in outbox_constraints


def test_worker_requires_explicit_provider_configuration(monkeypatch):
    monkeypatch.setattr(mail_worker,'get_settings',lambda:SimpleNamespace(email_enabled=False,
        resend_api_key='',notification_email_from='',public_app_origin=''))
    with pytest.raises(ValueError):mail_worker.validate_configuration()


def test_mail_is_suppressed_if_user_opted_out():
    u=uuid4()
    row=SimpleNamespace(recipient_id=u,notification_id=uuid4(),announcement_id=None)
    db=Mock()
    def get(model,identity):
        if model.__name__=='User':return SimpleNamespace(id=u,email='verified@example.org',status='active')
        if model.__name__=='EmailPreference':return SimpleNamespace(activity_enabled=False,releases_enabled=False)
        raise AssertionError('Notification body should not be read for opted-out user')
    db.get.side_effect=get
    assert mail_worker.payload_for(db,row) is None


def test_release_mail_requires_opt_in():
    u=uuid4()
    row=SimpleNamespace(recipient_id=u,notification_id=None,announcement_id=uuid4())
    db=Mock()
    def get(model,identity):
        if model.__name__=='User':return SimpleNamespace(id=u,email='verified@example.org',status='active')
        if model.__name__=='EmailPreference':return SimpleNamespace(activity_enabled=True,releases_enabled=False)
        raise AssertionError('Release content should not be read without opt-in')
    db.get.side_effect=get
    assert mail_worker.payload_for(db,row) is None


def test_migration_follows_notification_phase():
    from pathlib import Path
    source=(Path(__file__).parents[1]/'migrations/versions/0020_travel_email.py').read_text()
    assert "down_revision = '0019_notifications_trust'" in source
    assert 'AFTER INSERT ON user_notifications' in source
    assert 'AFTER INSERT ON platform_announcements' in source
