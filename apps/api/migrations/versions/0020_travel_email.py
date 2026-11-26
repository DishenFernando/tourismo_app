"""Durable, opt-in external mail delivery; routing is stateless.

Revision ID: 0020_travel_email
Revises: 0019_notifications_trust
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '0020_travel_email'
down_revision = '0019_notifications_trust'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('email_preferences',
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('activity_enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('releases_enabled', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_table('email_outbox',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('recipient_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('notification_id', UUID(as_uuid=True), sa.ForeignKey('user_notifications.id', ondelete='CASCADE')),
        sa.Column('announcement_id', UUID(as_uuid=True), sa.ForeignKey('platform_announcements.id', ondelete='CASCADE')),
        sa.Column('idempotency_key', sa.String(190), nullable=False, unique=True),
        sa.Column('state', sa.String(16), nullable=False, server_default='queued'),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('next_attempt_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('lease_until', sa.DateTime(timezone=True)),
        sa.Column('last_status', sa.String(80)),
        sa.Column('provider_id', sa.String(120)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('sent_at', sa.DateTime(timezone=True)),
        sa.CheckConstraint("state IN ('queued','sending','sent','failed','suppressed')", name='ck_email_outbox_state'),
        sa.CheckConstraint("(notification_id IS NOT NULL) <> (announcement_id IS NOT NULL)", name='ck_email_outbox_one_source'))
    op.create_index('ix_email_outbox_recipient_id', 'email_outbox', ['recipient_id'])
    op.create_index('ix_email_outbox_state', 'email_outbox', ['state'])
    op.create_index('ix_email_outbox_ready', 'email_outbox', ['state','next_attempt_at'])
    op.create_table('email_broadcast_jobs',
        sa.Column('announcement_id', UUID(as_uuid=True), sa.ForeignKey('platform_announcements.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('last_user_id', UUID(as_uuid=True)),
        sa.Column('finished', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))

    # Database triggers keep delivery work atomic with the in-app notification,
    # covering all business event flows without touching every route or risking
    # a lost email when a request process crashes after committing.
    op.execute("""
    CREATE FUNCTION tourismo_queue_notification_email() RETURNS trigger
    LANGUAGE plpgsql AS $$
    BEGIN
      INSERT INTO email_outbox(id, recipient_id, notification_id, idempotency_key,
                               state, attempts, next_attempt_at, created_at)
      VALUES (gen_random_uuid(), NEW.recipient_id, NEW.id,
              'notification:' || NEW.id::text, 'queued', 0, now(), now())
      ON CONFLICT (idempotency_key) DO NOTHING;
      RETURN NEW;
    END $$;
    """)
    op.execute("""
    CREATE TRIGGER trg_tourismo_notification_email
      AFTER INSERT ON user_notifications
      FOR EACH ROW EXECUTE FUNCTION tourismo_queue_notification_email();
    """)
    op.execute("""
    CREATE FUNCTION tourismo_queue_announcement_email() RETURNS trigger
    LANGUAGE plpgsql AS $$
    BEGIN
      INSERT INTO email_broadcast_jobs(announcement_id, finished, updated_at)
      VALUES (NEW.id, false, now()) ON CONFLICT DO NOTHING;
      RETURN NEW;
    END $$;
    """)
    op.execute("""
    CREATE TRIGGER trg_tourismo_announcement_email
      AFTER INSERT ON platform_announcements
      FOR EACH ROW EXECUTE FUNCTION tourismo_queue_announcement_email();
    """)


def downgrade():
    # This loses queued outbound mail. Back up before doing any downgrade.
    op.execute('DROP TRIGGER IF EXISTS trg_tourismo_notification_email ON user_notifications')
    op.execute('DROP FUNCTION IF EXISTS tourismo_queue_notification_email()')
    op.execute('DROP TRIGGER IF EXISTS trg_tourismo_announcement_email ON platform_announcements')
    op.execute('DROP FUNCTION IF EXISTS tourismo_queue_announcement_email()')
    op.drop_table('email_broadcast_jobs')
    op.drop_table('email_outbox')
    op.drop_table('email_preferences')
