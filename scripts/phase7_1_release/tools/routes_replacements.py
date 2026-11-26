"""Replacement function sources for precisely recognized Phase 7 routes."""
REPLACEMENTS = {}
REPLACEMENTS['ReviewWrite'] = '''class ReviewWrite(BaseModel):
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
'''
REPLACEMENTS['_review_dict'] = '''def _review_dict(row: CustomerReview, reply: CustomerReviewReply | None = None,
                 images: list[str] | None = None) -> dict:
    """Only non-identifying, publicly approved content reaches guests."""
    return {'id': str(row.id), 'rating': row.rating, 'title': row.title, 'body': row.body,
            'author_label': 'Tourismo traveler', 'visit_verified': False,
            'created_at': row.created_at.isoformat() if row.created_at else None,
            'images': images or [],
            'response': ({'body': reply.body, 'responded_at': reply.updated_at.isoformat()
                          if reply.updated_at else None} if reply and reply.state == 'published' else None)}
'''
REPLACEMENTS['_own_dict'] = '''def _own_dict(row: CustomerReview, images: list[str] | None = None) -> dict:
    return {'id': str(row.id), 'rating': row.rating, 'title': row.title, 'body': row.body,
            'state': row.state, 'moderation_note': row.moderation_note, 'images': images or []}
'''
REPLACEMENTS['listing_feedback'] = '''@public_router.get('/listings/{slug}')
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
'''
REPLACEMENTS['my_feedback'] = '''@public_router.get('/listings/{slug}/mine')
def my_feedback(slug: str, user: User = Depends(require_user), db: Session = Depends(get_db)):
    listing = _public_listing(db, slug)
    rows = db.scalars(select(CustomerReview).where(
        CustomerReview.listing_id == listing.id, CustomerReview.author_id == user.id)
        .order_by(CustomerReview.created_at.desc(), CustomerReview.id.desc()).limit(5)).all()
    photos = _image_links(db, [row.id for row in rows])
    my_reviews = [_own_dict(row, photos.get(row.id, [])) for row in rows]
    return {'reviews': my_reviews, 'review': my_reviews[0] if my_reviews else None,
            'remaining': max(0, 5 - len(my_reviews))}
'''
REPLACEMENTS['submit_feedback'] = '''@public_router.post('/listings/{slug}', status_code=201)
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
'''
REPLACEMENTS['provider_reviews'] = '''@vendor_router.get('/organizations/{org_id}/customer-reviews')
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
'''
