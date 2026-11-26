"""Phase 8 contract and abuse/ownership regression tests; no external Clerk required."""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.dialects.postgresql import dialect

from tourismo.core.models import ServiceEnquiry, ServiceEnquiryMessage, ServiceEnquiryReport
from tourismo.enquiries import routes as enquiries
from tourismo.main import app


def test_schema_uses_separate_enquiry_message_and_report_tables():
    assert [x.__tablename__ for x in (ServiceEnquiry,ServiceEnquiryMessage,ServiceEnquiryReport)] == [
        'service_enquiries','service_enquiry_messages','service_enquiry_reports']
    indexes={i.name for i in ServiceEnquiry.__table__.indexes}
    assert 'uq_service_enquiry_active' in indexes
    index=next(x for x in ServiceEnquiry.__table__.indexes if x.name=='uq_service_enquiry_active')
    assert index.unique
    assert 'open' in str(index.dialect_options['postgresql']['where'])
    assert 'answered' in str(index.dialect_options['postgresql']['where'])
    assert 'payment' not in ' '.join(x.name for x in ServiceEnquiry.__table__.columns)
    assert 'booking' not in ' '.join(x.name for x in ServiceEnquiry.__table__.columns)


@pytest.mark.parametrize('subject,message', [
    ('Short','Valid message containing enough descriptive content.'),
    ('A valid subject','too short'),
    ('A valid subject',' '*21),
    (' '*12,'Valid message containing enough descriptive content.'),
    ('A valid subject','x'*2001),
])
def test_invalid_create_payloads(subject,message):
    with pytest.raises(ValidationError):
        enquiries.NewEnquiry(subject=subject,message=message)


def test_injection_of_sender_roles_or_target_user_is_rejected():
    with pytest.raises(ValidationError):
        enquiries.NewMessage.model_validate({'body':'A useful question','sender_type':'vendor','sender_id':str(uuid4())})
    with pytest.raises(ValidationError):
        enquiries.NewEnquiry.model_validate({'subject':'Planning details','message':'Details for our upcoming travel group.', 'traveler_id':str(uuid4())})


def test_guest_cannot_read_or_mutate_private_enquiries():
    eid=str(uuid4());org=str(uuid4())
    with TestClient(app) as client:
        payload={'subject':'Planning in December','message':'Please share available options and indicative prices.'}
        assert client.post('/api/v1/enquiries/listings/real-listing',json=payload).status_code==401
        assert client.get('/api/v1/enquiries').status_code==401
        assert client.get(f'/api/v1/enquiries/{eid}').status_code==401
        assert client.post(f'/api/v1/enquiries/{eid}/messages',json={'body':'Anything available?'}).status_code==401
        assert client.post(f'/api/v1/enquiries/{eid}/withdraw').status_code==401
        assert client.post(f'/api/v1/enquiries/{eid}/reports',json={
            'reason':'spam','explanation':'Please review the conversation for spam.'}).status_code==401
        assert client.get(f'/api/v1/vendor/organizations/{org}/enquiries').status_code==401
        assert client.get(f'/api/v1/vendor/organizations/{org}/enquiries/{eid}').status_code==401
        assert client.post(f'/api/v1/vendor/organizations/{org}/enquiries/{eid}/messages',json={'body':'Some response here'}).status_code==401
        assert client.get('/api/v1/admin/enquiry-reports').status_code==401
        assert client.get(f'/api/v1/admin/enquiry-reports/{eid}/thread').status_code==401
        assert client.post(f'/api/v1/admin/enquiry-reports/{eid}/decision',json={
            'decision':'block_thread','reason':'This requires a safety intervention.'}).status_code==401


def test_own_query_contains_owner_filter():
    db=Mock();db.scalar.return_value=None
    user=SimpleNamespace(id=uuid4())
    with pytest.raises(HTTPException) as ex:
        enquiries._read_own(db,uuid4(),user)
    assert ex.value.status_code==404
    query=str(db.scalar.call_args.args[0].compile(dialect=dialect(),compile_kwargs={'literal_binds':True}))
    assert str(user.id) in query and 'service_enquiries.traveler_id' in query


def test_vendor_query_requires_membership_and_org_listing_link(monkeypatch):
    org_id=uuid4();eid=uuid4();user=SimpleNamespace(id=uuid4());db=Mock()
    checked=[]
    def check(_db,actual_org,actual_user,roles):
        checked.append((actual_org,actual_user,roles))
    monkeypatch.setattr(enquiries,'_organization',check)
    db.scalar.return_value=None
    with pytest.raises(HTTPException) as ex:
        enquiries._read_vendor(db,org_id,eid,user)
    assert ex.value.status_code==404
    assert checked==[(org_id,user,('owner','manager'))]
    query=str(db.scalar.call_args.args[0].compile(dialect=dialect(),compile_kwargs={'literal_binds':True}))
    assert str(org_id) in query and str(eid) in query
    assert 'service_listings.organization_id' in query


def test_vendor_denied_before_query_if_not_member(monkeypatch):
    db=Mock();user=SimpleNamespace(id=uuid4())
    def no_membership(*args,**kwargs):raise HTTPException(404,'Organization not found')
    monkeypatch.setattr(enquiries,'_organization',no_membership)
    with pytest.raises(HTTPException) as ex:
        enquiries._read_vendor(db,uuid4(),uuid4(),user)
    assert ex.value.status_code==404
    db.scalar.assert_not_called()


def test_profile_required_before_enquiry(monkeypatch):
    user=SimpleNamespace(id=uuid4(),profile_completed_at=None)
    db=Mock()
    with pytest.raises(HTTPException) as ex:
        enquiries.create_enquiry('hotel',enquiries.NewEnquiry(
            subject='Need information',message='Would you please tell me the options available?'),user,db)
    assert ex.value.status_code==403
    db.scalar.assert_not_called()


def test_unpublished_or_demo_listing_not_eligible(monkeypatch):
    user=SimpleNamespace(id=uuid4(),profile_completed_at=datetime.now(timezone.utc));db=Mock();db.scalar.return_value=None
    with pytest.raises(HTTPException) as ex:
        enquiries.create_enquiry('invented-demo',enquiries.NewEnquiry(
            subject='Need information',message='Would you please tell me the options available?'),user,db)
    assert ex.value.status_code==404
    db.commit.assert_not_called()


def test_vendor_member_cannot_send_traveler_enquiry_to_own_business(monkeypatch):
    user=SimpleNamespace(id=uuid4(),profile_completed_at=datetime.now(timezone.utc))
    listing=SimpleNamespace(id=uuid4(),organization_id=uuid4());db=Mock();db.scalar.return_value=listing
    monkeypatch.setattr(enquiries,'_is_affiliated',lambda *_:True)
    with pytest.raises(HTTPException) as ex:
        enquiries.create_enquiry('own-hotel',enquiries.NewEnquiry(
            subject='Need information',message='Would you please tell me the options available?'),user,db)
    assert ex.value.status_code==403


def test_daily_limit_rejects_spam(monkeypatch):
    user=SimpleNamespace(id=uuid4(),profile_completed_at=datetime.now(timezone.utc))
    listing=SimpleNamespace(id=uuid4(),organization_id=uuid4());db=Mock()
    db.scalar.side_effect=[listing,8]
    monkeypatch.setattr(enquiries,'_is_affiliated',lambda *_:False)
    with pytest.raises(HTTPException) as ex:
        enquiries.create_enquiry('hotel',enquiries.NewEnquiry(
            subject='Need information',message='Would you please tell me the options available?'),user,db)
    assert ex.value.status_code==429


def test_duplicate_open_enquiry_is_rejected(monkeypatch):
    user=SimpleNamespace(id=uuid4(),profile_completed_at=datetime.now(timezone.utc))
    listing=SimpleNamespace(id=uuid4(),organization_id=uuid4());db=Mock()
    db.scalar.side_effect=[listing,0,uuid4()]
    monkeypatch.setattr(enquiries,'_is_affiliated',lambda *_:False)
    with pytest.raises(HTTPException) as ex:
        enquiries.create_enquiry('hotel',enquiries.NewEnquiry(
            subject='Need information',message='Would you please tell me the options available?'),user,db)
    assert ex.value.status_code==409
    db.commit.assert_not_called()


@pytest.mark.parametrize('state',['closed','withdrawn','blocked'])
def test_closed_threads_cannot_receive_messages(state):
    with pytest.raises(HTTPException) as ex:
        enquiries._allow_reply(SimpleNamespace(state=state))
    assert ex.value.status_code==409


def test_thread_message_projection_does_not_include_private_contact_info():
    row=SimpleNamespace(id=uuid4(),sender_type='vendor',body='Availability is not confirmed.',
         sender_id=uuid4(),email='private@example.org',created_at=datetime.now(timezone.utc))
    assert set(enquiries._message_view(row))=={'id','sender','body','created_at'}
    assert 'private@example.org' not in str(enquiries._message_view(row))
    enquiry=SimpleNamespace(id=uuid4(),subject='Questions',state='open',created_at=None,updated_at=None,
                            traveler_id=uuid4())
    listing=SimpleNamespace(title='Test service',slug='test-service',organization_id=uuid4())
    assert set(enquiries._summary(enquiry,listing))=={'id','listing_slug','listing_title','subject','state','created_at','updated_at'}


def test_reporter_must_be_conversation_participant(monkeypatch):
    original=SimpleNamespace(id=uuid4(),listing_id=uuid4(),traveler_id=uuid4())
    listing=SimpleNamespace(organization_id=uuid4())
    db=Mock();db.get.side_effect=[original,listing]
    def reject(*args,**kwargs):raise HTTPException(404,'Organization not found')
    monkeypatch.setattr(enquiries,'_organization',reject)
    with pytest.raises(HTTPException) as ex:
        enquiries.report_enquiry(original.id,enquiries.NewReport(
            reason='privacy',explanation='Someone shared private information without consent.'),
            SimpleNamespace(id=uuid4()),db)
    assert ex.value.status_code==404
    db.commit.assert_not_called()


def test_admin_report_block_requires_reason_and_changes_thread_state():
    with pytest.raises(ValidationError):
        enquiries.ReportDecision(decision='block_thread',reason='short')
    report=SimpleNamespace(id=uuid4(),enquiry_id=uuid4(),state='open')
    enquiry=SimpleNamespace(id=report.enquiry_id,state='answered',updated_at=None)
    db=Mock();db.scalar.side_effect=[report,enquiry]
    admin=SimpleNamespace(id=uuid4())
    result=enquiries.moderate_report(report.id,enquiries.ReportDecision(
        decision='block_thread',reason='Reported harassment verified after review.'),admin,None,db)
    assert result=={'state':'actioned','thread_state':'blocked'}
    assert enquiry.state=='blocked'
    db.commit.assert_called_once()


def test_enquiry_routes_available_and_no_demo_endpoint():
    paths={(r.path,verb) for r in app.routes for verb in getattr(r,'methods',[])}
    assert {('/api/v1/enquiries','GET'),('/api/v1/enquiries/listings/{slug}','POST'),
            ('/api/v1/enquiries/{enquiry_id}','GET'),('/api/v1/enquiries/{enquiry_id}/messages','POST'),
            ('/api/v1/vendor/organizations/{org_id}/enquiries','GET'),
            ('/api/v1/admin/enquiry-reports','GET'),('/api/v1/admin/enquiry-reports/{report_id}/thread','GET')} <= paths
    assert not any('/demo/' in path and 'enquir' in path for path,verb in paths)
