"""Private tourist/provider enquiry threads (never bookings or payments).

Revision ID: 0018_service_enquiries
Revises: 0017_review_media
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '0018_service_enquiries'
down_revision = '0017_review_media'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('service_enquiries',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('listing_id', UUID(as_uuid=True), sa.ForeignKey('service_listings.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('traveler_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('subject', sa.String(140), nullable=False),
        sa.Column('state', sa.String(20), nullable=False, server_default='open'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("state IN ('open','answered','closed','withdrawn','blocked')", name='ck_service_enquiry_state'))
    op.create_index('ix_service_enquiries_listing_id', 'service_enquiries', ['listing_id'])
    op.create_index('ix_service_enquiries_traveler_id', 'service_enquiries', ['traveler_id'])
    op.create_index('ix_service_enquiries_state', 'service_enquiries', ['state'])
    op.create_index('ix_service_enquiry_traveler_created', 'service_enquiries', ['traveler_id', 'created_at'])
    op.create_index('uq_service_enquiry_active', 'service_enquiries', ['listing_id','traveler_id'],
                    unique=True, postgresql_where=sa.text("state IN ('open','answered')"))
    op.create_table('service_enquiry_messages',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('enquiry_id', UUID(as_uuid=True), sa.ForeignKey('service_enquiries.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('sender_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('sender_type', sa.String(12), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("sender_type IN ('traveler','vendor')", name='ck_service_enquiry_sender'))
    op.create_index('ix_service_enquiry_messages_enquiry_id', 'service_enquiry_messages', ['enquiry_id'])
    op.create_index('ix_service_enquiry_messages_page', 'service_enquiry_messages', ['enquiry_id','created_at','id'])
    op.create_index('ix_service_enquiry_message_sender_time', 'service_enquiry_messages', ['sender_id','created_at'])
    op.create_table('service_enquiry_reports',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('enquiry_id', UUID(as_uuid=True), sa.ForeignKey('service_enquiries.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('reporter_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('reason', sa.String(24), nullable=False),
        sa.Column('explanation', sa.String(600), nullable=False),
        sa.Column('state', sa.String(20), nullable=False, server_default='open'),
        sa.Column('reviewed_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='RESTRICT')),
        sa.Column('reviewed_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('enquiry_id','reporter_id',name='uq_service_enquiry_reporter'),
        sa.CheckConstraint("reason IN ('spam','abuse','privacy','misleading','other')", name='ck_service_enquiry_report_reason'),
        sa.CheckConstraint("state IN ('open','dismissed','actioned')", name='ck_service_enquiry_report_state'))
    op.create_index('ix_service_enquiry_reports_enquiry_id', 'service_enquiry_reports', ['enquiry_id'])
    op.create_index('ix_service_enquiry_reports_state', 'service_enquiry_reports', ['state'])


def downgrade():
    # Destructive: downgrading drops private enquiry history. Take a backup before any rollback.
    op.drop_table('service_enquiry_reports')
    op.drop_table('service_enquiry_messages')
    op.drop_table('service_enquiries')
