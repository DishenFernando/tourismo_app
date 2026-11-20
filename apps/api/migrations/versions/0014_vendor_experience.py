"""Phase 4.5 Part 2: local sanitized listing-photo storage.

Revision ID: 0014_vendor_experience
Revises: 0013_onboarding_media_ux
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '0014_vendor_experience'
down_revision = '0013_onboarding_media_ux'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('service_listing_image_blobs',
        sa.Column('photo_id', UUID(as_uuid=True),
                  sa.ForeignKey('service_listing_photos.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('content_type', sa.String(32), nullable=False),
        sa.Column('data', sa.LargeBinary(), nullable=False),
        sa.Column('sha256', sa.String(64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()))


def downgrade():
    op.drop_table('service_listing_image_blobs')
