"""Phase 7: contract, moderation, anti-self-review and privacy regression checks."""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.dialects.postgresql import dialect

from tourismo.core.database import get_db
from tourismo.core.models import CustomerReview, CustomerReviewReply, CustomerReviewReport
from tourismo.main import app
from tourismo.reviews import routes as feedback


def test_new_schema_is_separate_from_existing_listing_publication_reviews():
    assert CustomerReview.__tablename__ == 'customer_reviews'
    assert CustomerReviewReply.__tablename__ == 'customer_review_replies'
    assert CustomerReviewReport.__tablename__ == 'customer_review_reports'
    names = {name for t in (CustomerReview, CustomerReviewReply, CustomerReviewReport)
             for item in t.__table__.constraints for name in [item.name] if name}
    assert 'uq_customer_review_author_listing' not in names
    assert 'uq_customer_review_reporter' in names
    assert 'ck_customer_review_rating' in names
    assert 'ck_customer_review_state' in names
    assert 'ck_customer_review_reply_state' in names


@pytest.mark.parametrize('rating', [0, -1, 6, True, 2.5, '5', None])
def test_invalid_ratings_rejected(rating):
    with pytest.raises(ValidationError):
        feedback.ReviewWrite.model_validate({'rating':rating,'title':'Helpful','body':'The staff and facilities were satisfactory during our visit.'})


@pytest.mark.parametrize('payload', [
    {'rating':5,'title':'Hi','body':'The staff and facilities were satisfactory during our visit.'},
    {'rating':5,'title':'Good','body':'Too brief'},
    {'rating':5,'title':'Good','body':'x'*2001},
    {'rating':5,'title':'Good','body':'x'*32,'unknown':'secret'},
])
def test_invalid_review_content_rejected(payload):
    with pytest.raises(ValidationError):
        feedback.ReviewWrite.model_validate(payload)


@pytest.mark.parametrize('reason', ['made_up','',None])
def test_invalid_report_category_rejected(reason):
    with pytest.raises(ValidationError):
        feedback.ReportWrite.model_validate({'reason':reason,'explanation':'This information should be checked by moderators.'})


def test_author_must_complete_profile():
    db=Mock();listing=SimpleNamespace(organization_id=uuid4())
    user=SimpleNamespace(id=uuid4(),profile_completed_at=None)
    with pytest.raises(HTTPException) as err:
        feedback._eligible_author(db,user,listing)
    assert err.value.status_code==403
    assert db.scalar.call_count==0


def test_organization_owner_cannot_review_own_listing():
    owner=uuid4();org=uuid4();db=Mock();db.scalar.side_effect=[owner]
    assert feedback._is_affiliated(db, owner, org)
    assert db.scalar.call_count==1


def test_pending_or_active_vendor_members_cannot_review_own_listing():
    user=uuid4();org=uuid4();db=Mock();db.scalar.side_effect=[uuid4(),uuid4()]
    assert feedback._is_affiliated(db,user,org)
    query=str(db.scalar.call_args.args[0].compile(dialect=dialect(), compile_kwargs={'literal_binds':True}))
    assert 'vendor_memberships.state IN' in query
    assert "'active', 'pending'" in query


def test_unauthorized_public_mutation_endpoints_require_authentication():
    with TestClient(app) as client:
        slug='test-hotel'
        rid=str(uuid4())
        assert client.post(f'/api/v1/reviews/listings/{slug}',json={
            'rating':5,'title':'Nice stay','body':'The location and rooms were excellent, but not perfect.'}).status_code==401
        assert client.get(f'/api/v1/reviews/listings/{slug}/mine').status_code==401
        assert client.post(f'/api/v1/reviews/{rid}/reports',json={
            'reason':'spam','explanation':'Please review this spamlike customer comment.'}).status_code==401
        org=str(uuid4())
        assert client.get(f'/api/v1/vendor/organizations/{org}/customer-reviews').status_code==401
        assert client.post(f'/api/v1/vendor/organizations/{org}/customer-reviews/{rid}/response',json={
            'body':'Thank you for the useful customer feedback.'}).status_code==401
        assert client.get('/api/v1/admin/customer-reviews').status_code==401
        assert client.get('/api/v1/admin/customer-reviews/replies').status_code==401
        assert client.get('/api/v1/admin/customer-reviews/reports').status_code==401
        assert client.post(f'/api/v1/admin/customer-reviews/{rid}/decision',json={
            'decision':'published','reason':'Reviewed content meets our guidelines.'}).status_code==401


def test_public_review_projection_excludes_identity_and_private_moderation_data():
    review=SimpleNamespace(id=uuid4(),rating=3,title='Decent option',body='A useful place to stay',
        author_id=uuid4(),state='published',moderation_note='Sensitive internal information',
        created_at=datetime.now(timezone.utc))
    response=feedback._review_dict(review)
    assert response['visit_verified'] is False
    assert response['author_label']=='Tourismo traveler'
    assert set(response)=={'id','rating','title','body','author_label','visit_verified','created_at','images','response'}
    assert 'author_id' not in str(response)
    assert 'Sensitive' not in str(response)


def test_provider_reply_only_public_after_approval():
    review=SimpleNamespace(id=uuid4(),rating=5,title='Nice',body='Great',created_at=None)
    reply=SimpleNamespace(body='Thanks',state='pending',updated_at=None)
    assert feedback._review_dict(review,reply)['response'] is None
    reply.state='published'
    assert feedback._review_dict(review,reply)['response']['body']=='Thanks'


def test_editing_someone_elses_review_is_denied():
    writer=SimpleNamespace(id=uuid4())
    previous=SimpleNamespace(id=uuid4(),author_id=uuid4())
    db=Mock();db.scalar.return_value=previous
    with pytest.raises(HTTPException) as err:
        feedback.edit_feedback(previous.id,feedback.ReviewWrite(
            rating=4,title='A title',body='A review long enough to be useful and truthful.'),writer,db)
    assert err.value.status_code==404
    db.commit.assert_not_called()


def test_five_review_cap_refuses_sixth_submission(monkeypatch):
    author=SimpleNamespace(id=uuid4(),profile_completed_at=datetime.now(timezone.utc))
    listing=SimpleNamespace(id=uuid4(),organization_id=uuid4())
    db=Mock();db.scalar.side_effect=[author.id,5]
    monkeypatch.setattr(feedback,'_public_listing',lambda _db,_slug:listing)
    monkeypatch.setattr(feedback,'_eligible_author',lambda *_:None)
    with pytest.raises(HTTPException) as err:
        feedback.submit_feedback('hotel',feedback.ReviewWrite(
            rating=4,title='Detailed title',body='A very detailed updated account of this experience.'),author,db)
    assert err.value.status_code==409
    db.commit.assert_not_called()


def test_reporting_own_review_is_rejected():
    author=uuid4();review=SimpleNamespace(id=uuid4(),author_id=author,state='published')
    db=Mock();db.get.return_value=review
    with pytest.raises(HTTPException) as err:
        feedback.report_feedback(review.id,feedback.ReportWrite(
            reason='spam', explanation='Some text that describes the complaint.'),
            SimpleNamespace(id=author),db)
    assert err.value.status_code==403
    db.commit.assert_not_called()


def test_provider_response_enforces_organization_ownership(monkeypatch):
    org=SimpleNamespace(id=uuid4(),verification_state='approved')
    review=SimpleNamespace(id=uuid4(),state='published',listing_id=uuid4())
    db=Mock();db.get.side_effect=[review,SimpleNamespace(organization_id=uuid4())]
    monkeypatch.setattr(feedback,'_organization',lambda *_args:org)
    with pytest.raises(HTTPException) as err:
        feedback.provider_response(org.id,review.id,feedback.ReplyWrite(
            body='Thank you for sharing your thoughts and experience.'),SimpleNamespace(id=uuid4()),db)
    assert err.value.status_code==404


def test_report_moderation_hides_review_and_reply():
    reporter_id=uuid4();review_id=uuid4()
    report=SimpleNamespace(id=uuid4(),review_id=review_id,state='open')
    review=SimpleNamespace(id=review_id,state='published',author_id=uuid4())
    reply=SimpleNamespace(state='published')
    db=Mock();db.scalar.side_effect=[report,review];db.get.return_value=reply
    admin=SimpleNamespace(id=reporter_id)
    answer=feedback.decide_report(report.id, feedback.ReportDecision(
        decision='hide_review',reason='A published review contains private personal information.'),
        admin, None,db)
    assert answer['state']=='actioned'
    assert review.state=='hidden'
    assert reply.state=='hidden'
    db.commit.assert_called_once()


def test_reviews_routes_exist_and_demonstration_catalog_is_not_a_review_target():
    paths={(r.path,method) for r in app.routes for method in getattr(r,'methods',[])}
    required={
        ('/api/v1/reviews/listings/{slug}','GET'),
        ('/api/v1/reviews/listings/{slug}','POST'),
        ('/api/v1/reviews/{review_id}/reports','POST'),
        ('/api/v1/vendor/organizations/{org_id}/customer-reviews/{review_id}/response','POST'),
        ('/api/v1/admin/customer-reviews/{review_id}/decision','POST'),
        ('/api/v1/admin/customer-reviews/reports/{report_id}/decision','POST'),
    }
    assert required <= paths
    assert all(not path.startswith('/api/v1/demo/') for path, _ in required)


def test_published_review_query_is_limited_and_counted(monkeypatch):
    listing=SimpleNamespace(id=uuid4())
    monkeypatch.setattr(feedback,'_public_listing',lambda _db,slug:listing)
    db=Mock();db.scalar.side_effect=[3,4.333333]
    db.scalars.return_value.all.return_value=[]
    output=feedback.listing_feedback('sample',5,0,db)
    assert output['count']==3
    assert output['average_rating']==4.33
    compiled=str(db.scalar.call_args_list[0].args[0].compile(dialect=dialect()))
    assert 'customer_reviews.state =' in compiled


@pytest.mark.parametrize('payload', [
    {'rating':5,'title':'  A  ','body':'The staff and facilities were satisfactory during our visit.'},
    {'rating':5,'title':'Good','body':' ' * 36},
])
def test_blank_after_trimming_is_rejected(payload):
    with pytest.raises(ValidationError):
        feedback.ReviewWrite.model_validate(payload)


def test_unpublished_review_cannot_be_reported():
    review=SimpleNamespace(id=uuid4(),state='pending',author_id=uuid4())
    db=Mock();db.get.return_value=review
    with pytest.raises(HTTPException) as err:
        feedback.report_feedback(review.id,feedback.ReportWrite(
            reason='spam', explanation='Potential advertising content should be reviewed.'),
            SimpleNamespace(id=uuid4()),db)
    assert err.value.status_code==404


def test_admin_cannot_moderate_own_review():
    user=SimpleNamespace(id=uuid4())
    review=SimpleNamespace(id=uuid4(),author_id=user.id)
    db=Mock();db.scalar.return_value=review
    with pytest.raises(HTTPException) as err:
        feedback.decide_review(review.id,feedback.DecisionWrite(
            decision='published',reason='Review meets the applicable editorial guidelines.'),user,None,db)
    assert err.value.status_code==403
    db.commit.assert_not_called()


def test_report_decision_is_one_time_only():
    report=SimpleNamespace(id=uuid4(),state='dismissed')
    db=Mock();db.scalar.return_value=report
    with pytest.raises(HTTPException) as err:
        feedback.decide_report(report.id,feedback.ReportDecision(
            decision='hide_review',reason='The review contained personal information.'),
            SimpleNamespace(id=uuid4()),None,db)
    assert err.value.status_code==409
    db.commit.assert_not_called()
