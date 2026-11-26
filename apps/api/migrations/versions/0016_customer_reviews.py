"""Moderated customer feedback, provider replies, and abuse reports.

Revision ID: 0016_customer_reviews
Revises: 0015_location_links
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '0016_customer_reviews'
down_revision = '0015_location_links'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('customer_reviews',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('listing_id', UUID(as_uuid=True), sa.ForeignKey('service_listings.id', ondelete='CASCADE'), nullable=False),
        sa.Column('author_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('rating', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(120), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('state', sa.String(24), nullable=False, server_default='pending'),
        sa.Column('moderation_note', sa.String(600)),
        sa.Column('moderated_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='RESTRICT')),
        sa.Column('moderated_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('listing_id', 'author_id', name='uq_customer_review_author_listing'),
        sa.CheckConstraint('rating BETWEEN 1 AND 5', name='ck_customer_review_rating'),
        sa.CheckConstraint("state IN ('pending','published','changes_requested','hidden')", name='ck_customer_review_state'))
    op.create_index('ix_customer_reviews_listing_id', 'customer_reviews', ['listing_id'])
    op.create_index('ix_customer_reviews_author_id', 'customer_reviews', ['author_id'])
    op.create_index('ix_customer_reviews_state', 'customer_reviews', ['state'])
    op.create_index('ix_customer_review_listing_state', 'customer_reviews', ['listing_id', 'state'])
    op.create_table('customer_review_replies',
        sa.Column('review_id', UUID(as_uuid=True), sa.ForeignKey('customer_reviews.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('organization_id', UUID(as_uuid=True), sa.ForeignKey('vendor_organizations.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('author_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('state', sa.String(24), nullable=False, server_default='pending'),
        sa.Column('moderation_note', sa.String(600)),
        sa.Column('moderated_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='RESTRICT')),
        sa.Column('moderated_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("state IN ('pending','published','changes_requested','hidden')", name='ck_customer_review_reply_state'))
    op.create_index('ix_customer_review_replies_state', 'customer_review_replies', ['state'])
    op.create_table('customer_review_reports',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('review_id', UUID(as_uuid=True), sa.ForeignKey('customer_reviews.id', ondelete='CASCADE'), nullable=False),
        sa.Column('reporter_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('reason', sa.String(24), nullable=False),
        sa.Column('explanation', sa.String(600), nullable=False),
        sa.Column('state', sa.String(20), nullable=False, server_default='open'),
        sa.Column('reviewed_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='RESTRICT')),
        sa.Column('reviewed_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('review_id', 'reporter_id', name='uq_customer_review_reporter'),
        sa.CheckConstraint("reason IN ('spam','abuse','privacy','misleading','other')", name='ck_customer_review_report_reason'),
        sa.CheckConstraint("state IN ('open','dismissed','actioned')", name='ck_customer_review_report_state'))
    op.create_index('ix_customer_review_reports_review_id', 'customer_review_reports', ['review_id'])
    op.create_index('ix_customer_review_reports_state', 'customer_review_reports', ['state'])


def downgrade():
    op.drop_table('customer_review_reports')
    op.drop_table('customer_review_replies')
    op.drop_table('customer_reviews')
