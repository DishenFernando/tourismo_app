"""User-specific notifications and one-to-many release announcements.

Revision ID: 0019_notifications_trust
Revises: 0018_service_enquiries
No existing review, message or user records are modified.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '0019_notifications_trust'
down_revision = '0018_service_enquiries'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('user_notifications',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('recipient_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('kind', sa.String(48), nullable=False),
        sa.Column('title', sa.String(160), nullable=False),
        sa.Column('body', sa.String(600), nullable=False),
        sa.Column('target_url', sa.String(400), nullable=False),
        sa.Column('dedupe_key', sa.String(190), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('read_at', sa.DateTime(timezone=True)),
        sa.UniqueConstraint('recipient_id', 'dedupe_key', name='uq_user_notification_dedupe'),
        sa.CheckConstraint("char_length(title) > 0 AND char_length(body) > 0",name='ck_notification_nonempty'))
    op.create_index('ix_user_notification_inbox', 'user_notifications',
                    ['recipient_id','created_at'])
    op.create_index('ix_user_notification_unread', 'user_notifications',
                    ['recipient_id','read_at'])
    op.create_table('platform_announcements',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('release_key', sa.String(64), nullable=False, unique=True),
        sa.Column('title', sa.String(160), nullable=False),
        sa.Column('body', sa.String(600), nullable=False),
        sa.Column('target_url', sa.String(400), nullable=False),
        sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(timezone=True)),
        sa.CheckConstraint("char_length(title) > 0 AND char_length(body) > 0",name='ck_announcement_nonempty'))
    op.create_index('ix_platform_announcement_published', 'platform_announcements', ['published_at'])
    op.create_table('announcement_reads',
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('announcement_id', UUID(as_uuid=True), sa.ForeignKey('platform_announcements.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))


def downgrade():
    # Destructive to notification history only; backup first.
    op.drop_table('announcement_reads')
    op.drop_table('platform_announcements')
    op.drop_table('user_notifications')
