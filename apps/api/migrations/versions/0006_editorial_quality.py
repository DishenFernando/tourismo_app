"""Reviewable revisions that do not interrupt public published guides.

Revision ID: 0006_editorial_quality
Revises: 0005_rich_destination_review
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = '0006_editorial_quality'
down_revision = '0005_rich_destination_review'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('destination_guide_revisions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('guide_id', UUID(as_uuid=True), sa.ForeignKey('destination_guides.id', ondelete='CASCADE'), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('overview', sa.Text(), nullable=False),
        sa.Column('highlights', JSONB(), nullable=False),
        sa.Column('local_tips', JSONB(), nullable=False),
        sa.Column('source_id', UUID(as_uuid=True), sa.ForeignKey('content_sources.id')),
        sa.Column('status', sa.String(24), nullable=False, server_default='draft'),
        sa.Column('edited_by', UUID(as_uuid=True), sa.ForeignKey('users.id')),
        sa.Column('reviewed_by', UUID(as_uuid=True), sa.ForeignKey('users.id')),
        sa.Column('reviewed_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('guide_id', 'version', name='uq_guide_revision_version'))
    op.create_index('ix_destination_guide_revisions_guide_id', 'destination_guide_revisions', ['guide_id'])
    op.create_index('ix_destination_guide_revisions_status', 'destination_guide_revisions', ['status'])


def downgrade():
    # A rollback intentionally drops editorial draft/history data only; published guides remain intact.
    op.drop_table('destination_guide_revisions')
