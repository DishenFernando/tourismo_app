"""Phase 1: identity, geography, cloud trips, audit foundation.

Revision ID: 0001_foundation
Revises:
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
from tourismo.core.geo import Geography

revision = '0001_foundation'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute('CREATE EXTENSION IF NOT EXISTS postgis')
    op.execute('CREATE EXTENSION IF NOT EXISTS pg_trgm')
    op.create_table('users',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('auth_subject', sa.String(200), nullable=False, unique=True),
        sa.Column('display_name', sa.String(160)), sa.Column('email', sa.String(320)),
        sa.Column('locale', sa.String(10), nullable=False, server_default='en'),
        sa.Column('status', sa.String(24), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_table('platform_roles',
        sa.Column('id', UUID(as_uuid=True), primary_key=True), sa.Column('key', sa.String(50), unique=True, nullable=False),
        sa.Column('description', sa.Text, nullable=False))
    op.create_table('user_role_assignments',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('role_id', UUID(as_uuid=True), sa.ForeignKey('platform_roles.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('scope_type', sa.String(32), nullable=False, server_default='platform'),
        sa.Column('scope_id', UUID(as_uuid=True)),
        sa.Column('granted_by', UUID(as_uuid=True), sa.ForeignKey('users.id')),
        sa.Column('expires_at', sa.DateTime(timezone=True)))
    op.create_index('ix_user_role_scope', 'user_role_assignments', ['user_id', 'role_id', 'scope_type', 'scope_id'])
    op.create_table('content_sources',
        sa.Column('id', UUID(as_uuid=True), primary_key=True), sa.Column('name', sa.String(160), nullable=False),
        sa.Column('url', sa.String(2048)), sa.Column('license_status', sa.String(40), server_default='not_assessed', nullable=False),
        sa.Column('verified_at', sa.DateTime(timezone=True)))
    op.create_table('destinations',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('slug', sa.String(120), unique=True, nullable=False),
        sa.Column('district', sa.String(120), nullable=False),
        sa.Column('province', sa.String(120), nullable=False),
        sa.Column('location', Geography()),
        sa.Column('content_status', sa.String(30), server_default='draft', nullable=False),
        sa.Column('source_id', UUID(as_uuid=True), sa.ForeignKey('content_sources.id')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index('ix_destinations_district', 'destinations', ['district'])
    op.create_index('ix_destinations_content_status', 'destinations', ['content_status'])
    op.create_index('ix_destinations_location_gist', 'destinations', ['location'], postgresql_using='gist')
    op.create_table('destination_translations',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('destination_id', UUID(as_uuid=True), sa.ForeignKey('destinations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('locale', sa.String(10), nullable=False),
        sa.Column('title', sa.String(160), nullable=False), sa.Column('summary', sa.Text, nullable=False, server_default=''),
        sa.UniqueConstraint('destination_id', 'locale', name='uq_destination_locale'))
    op.create_table('trips',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('owner_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('client_draft_id', UUID(as_uuid=True), nullable=False),
        sa.Column('destination_slug', sa.String(120), sa.ForeignKey('destinations.slug', ondelete='RESTRICT'), nullable=False),
        sa.Column('title', sa.String(160), nullable=False),
        sa.Column('start_date', sa.Date), sa.Column('end_date', sa.Date),
        sa.Column('adults', sa.Integer, nullable=False),
        sa.Column('children_ages', JSONB, nullable=False, server_default='[]'),
        sa.Column('currency', sa.String(3), nullable=False, server_default='LKR'),
        sa.Column('budget_limit_minor', sa.BigInteger),
        sa.Column('budget_flexible', sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column('budget_items', JSONB, nullable=False, server_default='[]'),
        sa.Column('itinerary', JSONB, nullable=False, server_default='[]'),
        sa.Column('version', sa.Integer, nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('owner_id', 'client_draft_id', name='uq_trip_owner_draft'),
        sa.CheckConstraint('adults >= 1 AND adults <= 30', name='trip_adults_range'),
        sa.CheckConstraint('budget_limit_minor IS NULL OR budget_limit_minor >= 0', name='trip_budget_nonnegative'),
        sa.CheckConstraint('end_date IS NULL OR start_date IS NULL OR end_date >= start_date', name='trip_valid_dates'))
    op.create_index('ix_trips_owner_id', 'trips', ['owner_id'])
    op.create_table('audit_events',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('actor_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='RESTRICT')),
        sa.Column('action', sa.String(120), nullable=False),
        sa.Column('object_type', sa.String(60), nullable=False),
        sa.Column('object_id', UUID(as_uuid=True)), sa.Column('reason', sa.String(300)),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_index('ix_audit_events_action', 'audit_events', ['action'])
    op.create_index('ix_audit_events_occurred_at', 'audit_events', ['occurred_at'])

    # Place-name-only examples. No fabricated vendor, price, weather, or review records.
    # Each record stays labeled SAMPLE until a human-reviewed content release.
    for slug, title, district, province in [
        ('nuwara-eliya', 'Nuwara Eliya', 'Nuwara Eliya', 'Central'),
        ('anuradhapura', 'Anuradhapura', 'Anuradhapura', 'North Central'),
        ('kandy', 'Kandy', 'Kandy', 'Central'),
        ('galle', 'Galle', 'Galle', 'Southern'),
        ('ella', 'Ella', 'Badulla', 'Uva'),
    ]:
        destination_id = str(__import__('uuid').uuid4())
        translation_id = str(__import__('uuid').uuid4())
        op.execute(sa.text('''INSERT INTO destinations (id,slug,district,province,content_status)
                              VALUES (CAST(:id AS UUID),:slug,:district,:province,'sample')''').bindparams(
            id=destination_id, slug=slug, district=district, province=province))
        op.execute(sa.text('''INSERT INTO destination_translations (id,destination_id,locale,title,summary)
                              VALUES (CAST(:id AS UUID),CAST(:destination_id AS UUID),'en',:title,'Editorial guide pending source verification.')''').bindparams(
            id=translation_id, destination_id=destination_id, title=title))


def downgrade():
    op.drop_table('audit_events')
    op.drop_table('trips')
    op.drop_table('destination_translations')
    op.drop_table('destinations')
    op.drop_table('content_sources')
    op.drop_table('user_role_assignments')
    op.drop_table('platform_roles')
    op.drop_table('users')
