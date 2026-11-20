"""Tourism listings, credited media and independent publication reviews.

Revision ID: 0010_service_listings
Revises: 0009_vendor_documents
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = '0010_service_listings'
down_revision = '0009_vendor_documents'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('service_listings',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('organization_id', UUID(as_uuid=True), sa.ForeignKey('vendor_organizations.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('slug', sa.String(150), nullable=False, unique=True),
        sa.Column('category', sa.String(32), nullable=False),
        sa.Column('title', sa.String(160), nullable=False),
        sa.Column('summary', sa.String(350), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('province', sa.String(120), nullable=False),
        sa.Column('district', sa.String(120), nullable=False),
        sa.Column('public_email', sa.String(320)),
        sa.Column('public_phone', sa.String(40)),
        sa.Column('details', JSONB(), nullable=False),
        sa.Column('status', sa.String(24), nullable=False, server_default='draft'),
        sa.Column('review_feedback', sa.String(600)),
        sa.Column('published_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("category IN ('accommodation','restaurant','guide','transport','tour_operator','activity')", name='ck_service_listing_category'),
        sa.CheckConstraint("status IN ('draft','submitted','changes_requested','published','archived')", name='ck_service_listing_status'))
    op.create_index('ix_service_listings_organization_id', 'service_listings', ['organization_id'])
    op.create_index('ix_service_listings_category', 'service_listings', ['category'])
    op.create_index('ix_service_listings_status', 'service_listings', ['status'])
    op.create_index('ix_service_listing_location', 'service_listings', ['province', 'district'])
    op.create_table('service_listing_photos',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('listing_id', UUID(as_uuid=True), sa.ForeignKey('service_listings.id', ondelete='CASCADE'), nullable=False),
        sa.Column('image_url', sa.String(2048), nullable=False),
        sa.Column('source_url', sa.String(2048), nullable=False),
        sa.Column('credit', sa.String(160), nullable=False),
        sa.Column('license_name', sa.String(100), nullable=False),
        sa.Column('license_url', sa.String(2048), nullable=False),
        sa.Column('alt_text', sa.String(240), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('listing_id', 'source_url', name='uq_service_listing_photo_source'))
    op.create_index('ix_service_listing_photos_listing_id', 'service_listing_photos', ['listing_id'])
    op.create_table('service_listing_reviews',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('listing_id', UUID(as_uuid=True), sa.ForeignKey('service_listings.id', ondelete='CASCADE'), nullable=False),
        sa.Column('reviewer_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('decision', sa.String(24), nullable=False),
        sa.Column('reason', sa.String(600), nullable=False),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("decision IN ('published','changes_requested')", name='ck_listing_review_decision'))
    op.create_index('ix_service_listing_reviews_listing_id', 'service_listing_reviews', ['listing_id'])


def downgrade():
    # Only for disposable development environments: permanently deletes listing data.
    op.drop_table('service_listing_reviews')
    op.drop_table('service_listing_photos')
    op.drop_table('service_listings')
