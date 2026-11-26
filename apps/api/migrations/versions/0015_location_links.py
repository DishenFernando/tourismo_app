"""Add provenance for published destination and attraction coordinates.

Revision ID: 0015_location_links
Revises: 0014_vendor_experience
"""
from alembic import op
import sqlalchemy as sa

revision = '0015_location_links'
down_revision = '0014_vendor_experience'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('destinations', sa.Column('location_source_url', sa.String(2048), nullable=True))
    op.add_column('poi', sa.Column('location_source_url', sa.String(2048), nullable=True))


def downgrade():
    op.drop_column('poi', 'location_source_url')
    op.drop_column('destinations', 'location_source_url')
