"""Progressive vendor onboarding and transparently labelled editorial media.

Revision ID: 0013_onboarding_media_ux
Revises: 0012_listing_discovery_indexes
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '0013_onboarding_media_ux'
down_revision = '0012_listing_discovery_indexes'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('vendor_organizations', 'province', existing_type=sa.String(120), nullable=True)
    op.alter_column('vendor_organizations', 'district', existing_type=sa.String(120), nullable=True)
    op.alter_column('vendor_organizations', 'operating_address', existing_type=sa.Text(), nullable=True)
    op.add_column('destination_photos', sa.Column('media_kind', sa.String(24), nullable=False,
        server_default='commons_photo'))
    op.create_check_constraint('ck_destination_photo_media_kind', 'destination_photos',
        "media_kind IN ('commons_photo','owned_photo','ai_illustration')")
    op.create_table('destination_image_blobs',
        sa.Column('photo_id', UUID(as_uuid=True), sa.ForeignKey('destination_photos.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('content_type', sa.String(32), nullable=False),
        sa.Column('data', sa.LargeBinary(), nullable=False),
        sa.Column('sha256', sa.String(64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True))


def downgrade():
    # Downgrade may fail until incomplete vendor drafts are completed or removed.
    op.drop_table('destination_image_blobs')
    op.drop_constraint('ck_destination_photo_media_kind', 'destination_photos', type_='check')
    op.drop_column('destination_photos', 'media_kind')
    op.alter_column('vendor_organizations', 'operating_address', existing_type=sa.Text(), nullable=False)
    op.alter_column('vendor_organizations', 'district', existing_type=sa.String(120), nullable=False)
    op.alter_column('vendor_organizations', 'province', existing_type=sa.String(120), nullable=False)
