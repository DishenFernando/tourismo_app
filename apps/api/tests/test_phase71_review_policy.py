# Copy contents into apps/api/tests/test_phase71_review_policy.py
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from tourismo.core.models import CustomerReview, CustomerReviewImage
from tourismo.reviews import routes as reviews
from tourismo.reviews.safety import moderate_content, normalize_images


def test_five_review_limit_is_enforced_before_any_creation(monkeypatch):
    user = SimpleNamespace(id=uuid4(), profile_completed_at=datetime.now(timezone.utc))
    listing = SimpleNamespace(id=uuid4(), organization_id=uuid4())
    db = Mock()
    db.scalar.side_effect = [user.id, 5]
    monkeypatch.setattr(reviews, '_public_listing', lambda *_: listing)
    monkeypatch.setattr(reviews, '_eligible_author', lambda *_: None)
    with pytest.raises(HTTPException) as exc:
        reviews.submit_feedback('example', reviews.ReviewWrite(
            rating=4, title='Thoughtful review', body='The room was comfortable and the staff were friendly.'), user, db)
    assert exc.value.status_code == 409
    assert 'five' in exc.value.detail
    db.add.assert_not_called()


def test_four_reviews_allow_fifth_submission(monkeypatch):
    user = SimpleNamespace(id=uuid4(), profile_completed_at=datetime.now(timezone.utc))
    listing = SimpleNamespace(id=uuid4(), organization_id=uuid4())
    db = Mock()
    db.scalar.side_effect = [user.id, 4]
    monkeypatch.setattr(reviews, '_public_listing', lambda *_: listing)
    monkeypatch.setattr(reviews, '_eligible_author', lambda *_: None)
    monkeypatch.setattr(reviews, '_save_review', lambda *a, **k: {'review': {'state':'published'}})
    response = reviews.submit_feedback('example', reviews.ReviewWrite(
        rating=5, title='Useful details', body='The staff were helpful, and the facilities met expectations.'), user, db)
    assert response['review']['state'] == 'published'


def test_strict_photo_input_and_count_limits():
    with pytest.raises(HTTPException) as err:
        normalize_images(['data:image/svg+xml;base64,AA=='])
    assert err.value.status_code == 422
    with pytest.raises(HTTPException) as err:
        normalize_images(['invalid'] * 6)
    assert err.value.status_code == 422


def test_image_less_moderation_fail_closed(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    assert moderate_content('Good review', 'The place was welcoming.', []) == 'pending'
    with pytest.raises(HTTPException) as err:
        moderate_content('Good review', 'The place was welcoming.', [b'fake-jpeg'])
    assert err.value.status_code == 503


def test_photos_are_privately_gated_by_review_state():
    db=Mock()
    image=SimpleNamespace(id=uuid4(), review_id=uuid4(), jpeg_data=b'private')
    db.get.side_effect=[image,SimpleNamespace(state='pending')]
    with pytest.raises(HTTPException) as err:
        reviews.public_review_image(image.id,db)
    assert err.value.status_code==404


def test_profile_required_for_reviews():
    user=SimpleNamespace(id=uuid4(),profile_completed_at=None)
    listing=SimpleNamespace(organization_id=uuid4())
    with pytest.raises(HTTPException) as err:
        reviews._eligible_author(Mock(),user,listing)
    assert err.value.status_code==403


def test_new_review_photo_table_is_a_distinct_attachment_entity():
    assert CustomerReview.__tablename__=='customer_reviews'
    assert CustomerReviewImage.__tablename__=='customer_review_images'
    assert 'jpeg_data' in CustomerReviewImage.__table__.columns
    assert 'uq_customer_review_author_listing' not in {
        c.name for c in CustomerReview.__table__.constraints if c.name
    }
