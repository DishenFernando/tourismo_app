"""Add editable tourist profile fields without changing initial users or trips.

Revision ID: 0002_tourist_profiles
Revises: 0001_foundation
"""
from alembic import op
import sqlalchemy as sa

revision = '0002_tourist_profiles'
down_revision = '0001_foundation'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('home_region', sa.String(120), nullable=True))
    op.add_column('users', sa.Column('bio', sa.String(500), nullable=True))
    op.add_column('users', sa.Column('profile_completed_at', sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column('users', 'profile_completed_at')
    op.drop_column('users', 'bio')
    op.drop_column('users', 'home_region')
