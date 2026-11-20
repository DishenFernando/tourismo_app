"""Partial indexes for verified published geographic service discovery.

Revision ID: 0012_listing_discovery_indexes
Revises: 0011_advanced_listings
"""
from alembic import op
import sqlalchemy as sa

revision = '0012_listing_discovery_indexes'
down_revision = '0011_advanced_listings'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index('ix_service_listing_public_regions', 'service_listings',
                    ['province', 'district', 'published_at'],
                    postgresql_where=sa.text("status = 'published'"))
    op.execute('''CREATE INDEX ix_service_listing_public_geo ON service_listings
        USING GIST ((ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography))
        WHERE status = 'published' AND longitude IS NOT NULL AND latitude IS NOT NULL''')


def downgrade():
    op.drop_index('ix_service_listing_public_geo', table_name='service_listings')
    op.drop_index('ix_service_listing_public_regions', table_name='service_listings')
