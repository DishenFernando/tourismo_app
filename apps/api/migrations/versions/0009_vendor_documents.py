"""Private evidence uploads and license-expiry status; additive only."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '0009_vendor_documents'
down_revision = '0008_vendor_onboarding'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('vendor_documents',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('organization_id', UUID(as_uuid=True), sa.ForeignKey('vendor_organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('evidence_id', UUID(as_uuid=True), sa.ForeignKey('vendor_evidence.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('uploaded_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('original_name', sa.String(120), nullable=False),
        sa.Column('media_type', sa.String(60), nullable=False),
        sa.Column('storage_key', sa.String(64), nullable=False, unique=True),
        sa.Column('sha256', sa.String(64), nullable=False),
        sa.Column('size_bytes', sa.Integer(), nullable=False),
        sa.Column('scan_state', sa.String(20), nullable=False, server_default='pending_scan'),
        sa.Column('uploaded_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('deleted_at', sa.DateTime(timezone=True)),
        sa.CheckConstraint("scan_state IN ('pending_scan','clean','infected')", name='ck_vendor_document_scan'),
        sa.CheckConstraint('size_bytes > 0 AND size_bytes <= 5242880', name='ck_vendor_document_size'))
    op.create_index('ix_vendor_documents_organization_id','vendor_documents',['organization_id'])
    # We never DROP an existing organization table or mutate data in this migration.
    op.drop_constraint('ck_vendor_state', 'vendor_organizations', type_='check')
    op.create_check_constraint('ck_vendor_state', 'vendor_organizations',
        "verification_state IN ('draft','submitted','changes_requested','approved','rejected','expired_license')")


def downgrade():
    # Reject downgrade if any expired_license row remains; data and files require archival.
    op.drop_constraint('ck_vendor_state','vendor_organizations',type_='check')
    op.create_check_constraint('ck_vendor_state','vendor_organizations',
        "verification_state IN ('draft','submitted','changes_requested','approved','rejected')")
    op.drop_table('vendor_documents')
