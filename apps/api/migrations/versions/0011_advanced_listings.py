"""Advanced listing locations and safe private revisions.

Revision ID: 0011_advanced_listings
Revises: 0010_service_listings
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = '0011_advanced_listings'
down_revision = '0010_service_listings'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('service_listings', sa.Column('latitude', sa.Float()))
    op.add_column('service_listings', sa.Column('longitude', sa.Float()))
    op.add_column('service_listings', sa.Column('location_source_url', sa.String(2048)))
    op.add_column('service_listings', sa.Column('location_note', sa.String(250)))
    op.create_check_constraint('ck_listing_coordinate_pair', 'service_listings',
        '(latitude IS NULL AND longitude IS NULL AND location_source_url IS NULL) OR '
        '(latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180 AND location_source_url IS NOT NULL)')
    op.create_table('service_listing_revisions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('listing_id', UUID(as_uuid=True), sa.ForeignKey('service_listings.id', ondelete='CASCADE'), nullable=False),
        sa.Column('author_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('reviewer_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='RESTRICT')),
        sa.Column('status', sa.String(24), nullable=False, server_default='draft'),
        sa.Column('snapshot', JSONB(), nullable=False),
        sa.Column('review_feedback', sa.String(600)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('reviewed_at', sa.DateTime(timezone=True)),
        sa.CheckConstraint("status IN ('draft','submitted','changes_requested','approved')", name='ck_service_listing_revision_status'))
    op.create_index('ix_service_listing_revisions_listing_id', 'service_listing_revisions', ['listing_id'])
    op.create_index('ix_listing_revision_pending', 'service_listing_revisions', ['listing_id'],
        unique=True, postgresql_where=sa.text("status IN ('draft','submitted','changes_requested')"))


def downgrade():
    # CAUTION: destructive in non-disposable databases; no data downgrade in production.
    op.drop_table('service_listing_revisions')
    op.drop_constraint('ck_listing_coordinate_pair','service_listings',type_='check')
    for name in ('location_note','location_source_url','longitude','latitude'):
        op.drop_column('service_listings', name)
