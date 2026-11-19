"""Private vendor applicants, scoped team membership, evidence references, review history.

Revision ID: 0008_vendor_onboarding
Revises: 0007_pilot_destination_guides
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '0008_vendor_onboarding'
down_revision = '0007_pilot_destination_guides'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('vendor_organizations',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('owner_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('category', sa.String(32), nullable=False),
        sa.Column('business_name', sa.String(160), nullable=False),
        sa.Column('registration_no', sa.String(120), unique=True),
        sa.Column('contact_email', sa.String(320), nullable=False),
        sa.Column('contact_phone', sa.String(40)),
        sa.Column('province', sa.String(120), nullable=False),
        sa.Column('district', sa.String(120), nullable=False),
        sa.Column('operating_address', sa.Text(), nullable=False),
        sa.Column('license_no', sa.String(120)),
        sa.Column('verification_state', sa.String(24), nullable=False, server_default='draft'),
        sa.Column('reviewer_id', UUID(as_uuid=True), sa.ForeignKey('users.id')),
        sa.Column('reviewed_at', sa.DateTime(timezone=True)),
        sa.Column('review_feedback', sa.String(600)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("category IN ('accommodation','restaurant','guide','transport','tour_operator','activity')", name='ck_vendor_category'),
        sa.CheckConstraint("verification_state IN ('draft','submitted','changes_requested','approved','rejected')", name='ck_vendor_state'))
    op.create_index('ix_vendor_organizations_owner_id', 'vendor_organizations', ['owner_id'])
    op.create_index('ix_vendor_organizations_verification_state','vendor_organizations',['verification_state'])
    op.create_table('vendor_memberships',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('organization_id', UUID(as_uuid=True), sa.ForeignKey('vendor_organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('role', sa.String(16), nullable=False),
        sa.Column('state', sa.String(16), nullable=False, server_default='pending'),
        sa.Column('invited_by', UUID(as_uuid=True), sa.ForeignKey('users.id')),
        sa.Column('accepted_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('organization_id','user_id',name='uq_vendor_org_member'),
        sa.CheckConstraint("role IN ('owner','manager','staff')", name='ck_vendor_member_role'),
        sa.CheckConstraint("state IN ('pending','active','revoked')", name='ck_vendor_member_state'))
    op.create_index('ix_vendor_memberships_organization_id','vendor_memberships',['organization_id'])
    op.create_index('ix_vendor_memberships_user_id','vendor_memberships',['user_id'])
    op.create_table('vendor_evidence',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('organization_id', UUID(as_uuid=True), sa.ForeignKey('vendor_organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('evidence_type', sa.String(32), nullable=False),
        sa.Column('issuer', sa.String(160), nullable=False),
        sa.Column('reference_number', sa.String(160), nullable=False),
        sa.Column('expires_on', sa.Date()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('organization_id','evidence_type','reference_number',name='uq_vendor_evidence_ref'))
    op.create_index('ix_vendor_evidence_organization_id','vendor_evidence',['organization_id'])
    op.create_table('vendor_verification_checks',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('organization_id', UUID(as_uuid=True), sa.ForeignKey('vendor_organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('reviewer_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('decision', sa.String(24), nullable=False),
        sa.Column('reason', sa.String(600), nullable=False),
        sa.Column('source_url', sa.String(2048)),
        sa.Column('checked_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_index('ix_vendor_verification_checks_organization_id','vendor_verification_checks',['organization_id'])


def downgrade():
    # Downgrade destroys vendor applications and reviews; take a backup before doing so.
    op.drop_table('vendor_verification_checks')
    op.drop_table('vendor_evidence')
    op.drop_table('vendor_memberships')
    op.drop_table('vendor_organizations')
