"""Phase 2.1: sourced public destination guides and points of interest.

Seed entries are explicitly SAMPLE, not human-verified publications.
No prices, opening times, images, or exact POI coordinates are fabricated.

Revision ID: 0003_destination_intelligence
Revises: 0002_tourist_profiles
"""
import uuid
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
from tourismo.core.geo import Geography

revision = '0003_destination_intelligence'
down_revision = '0002_tourist_profiles'
branch_labels = None
depends_on = None


# Reference links verified during development. No media is imported or sublicensed.
SAMPLES = (
    ('anuradhapura', 'sacred-city-anuradhapura', 'Sacred City of Anuradhapura',
     'https://whc.unesco.org/en/list/200/',
     'Anuradhapura is a UNESCO World Heritage site associated with Sri Lanka\'s early Buddhist history and former royal capital.',
     ['UNESCO-listed sacred city', 'Historic monasteries and monuments'],
     'heritage', 'The UNESCO-listed sacred city encompasses ancient religious and civic heritage.'),
    ('galle', 'old-town-galle-fort', 'Old Town of Galle and its Fortifications',
     'https://whc.unesco.org/en/list/451/',
     'Galle Fort is a UNESCO World Heritage historic town with fortifications reflecting South Asian and European architectural traditions.',
     ['UNESCO-listed fortified old town', 'Historic coastal setting'],
     'heritage', 'The UNESCO site includes the historic old town and fortifications of Galle.'),
    ('kandy', 'sacred-city-kandy', 'Sacred City of Kandy',
     'https://whc.unesco.org/en/list/450/',
     'Kandy is a UNESCO World Heritage sacred city and the location of the Temple of the Tooth Relic.',
     ['UNESCO-listed sacred city', 'Temple of the Tooth Relic heritage'],
     'heritage', 'The UNESCO-listed sacred city includes the renowned Temple of the Tooth Relic.'),
    ('nuwara-eliya', 'gregory-lake', 'Gregory Lake',
     'https://nuwaraeliya.mc.gov.lk/index.php/information/about',
     'Nuwara Eliya is a hill-country city known for its cool climate, parks and Gregory Lake, a local recreational landmark.',
     ['Gregory Lake', 'Victoria Park'],
     'nature', 'Gregory Lake is a recreational landmark described by the Nuwara Eliya Municipal Council.'),
    ('ella', 'nine-arches-bridge', 'Nine Arches Railway Bridge',
     'https://visituva.lk/zone/ella',
     'Ella is a highland destination in Uva Province known for hiking, rail travel and scenic viewpoints.',
     ['Nine Arches Railway Bridge', 'Hill-country walks and viewpoints'],
     'landmark', 'Nine Arches Railway Bridge is listed among Ella attractions by the Uva tourism portal.'),
)


def _sample_uuid(value: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, 'tourismo:phase2:' + value))


def upgrade():
    op.create_table('destination_guides',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('destination_id', UUID(as_uuid=True), sa.ForeignKey('destinations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('locale', sa.String(10), nullable=False),
        sa.Column('overview', sa.Text, nullable=False),
        sa.Column('highlights', JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column('local_tips', JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column('content_status', sa.String(30), nullable=False, server_default='draft'),
        sa.Column('source_id', UUID(as_uuid=True), sa.ForeignKey('content_sources.id')),
        sa.Column('verified_at', sa.DateTime(timezone=True)),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('destination_id', 'locale', name='uq_destination_guide_locale'))
    op.create_index('ix_destination_guides_destination_id', 'destination_guides', ['destination_id'])
    op.create_index('ix_destination_guides_content_status', 'destination_guides', ['content_status'])
    op.create_table('poi',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('destination_id', UUID(as_uuid=True), sa.ForeignKey('destinations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('slug', sa.String(120), nullable=False),
        sa.Column('category', sa.String(40), nullable=False),
        sa.Column('location', Geography()),
        sa.Column('content_status', sa.String(30), nullable=False, server_default='draft'),
        sa.Column('source_id', UUID(as_uuid=True), sa.ForeignKey('content_sources.id')),
        sa.Column('verified_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('destination_id', 'slug', name='uq_poi_destination_slug'))
    op.create_index('ix_poi_destination_id', 'poi', ['destination_id'])
    op.create_index('ix_poi_category', 'poi', ['category'])
    op.create_index('ix_poi_content_status', 'poi', ['content_status'])
    op.create_index('ix_poi_location_gist', 'poi', ['location'], postgresql_using='gist')
    op.create_table('poi_translations',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('poi_id', UUID(as_uuid=True), sa.ForeignKey('poi.id', ondelete='CASCADE'), nullable=False),
        sa.Column('locale', sa.String(10), nullable=False),
        sa.Column('title', sa.String(160), nullable=False),
        sa.Column('description', sa.Text, nullable=False, server_default=''),
        sa.Column('local_tips', sa.Text, nullable=False, server_default=''),
        sa.UniqueConstraint('poi_id', 'locale', name='uq_poi_locale'))

    for slug, poi_slug, title, url, overview, highlights, category, description in SAMPLES:
        source_id = _sample_uuid(f'source:{slug}')
        guide_id = _sample_uuid(f'guide:{slug}')
        poi_id = _sample_uuid(f'poi:{slug}')
        translated_poi_id = _sample_uuid(f'poi-translation:{slug}')
        source_name = ('Nuwara Eliya Municipal Council' if slug == 'nuwara-eliya' else
                       'Uva Tourism Portal' if slug == 'ella' else 'UNESCO World Heritage Centre')
        op.execute(sa.text('''INSERT INTO content_sources (id, name, url, license_status)
            VALUES (CAST(:id AS UUID), :source_name, :url, 'reference_link_only')
            ON CONFLICT (id) DO NOTHING''').bindparams(id=source_id, url=url, source_name=source_name))
        op.execute(sa.text('''INSERT INTO destination_guides
            (id, destination_id, locale, overview, highlights, local_tips, content_status, source_id)
            SELECT CAST(:id AS UUID), d.id, 'en', :overview, CAST(:highlights AS jsonb),
                   '[]'::jsonb, 'sample', CAST(:source_id AS UUID)
            FROM destinations d WHERE d.slug = :slug
            ON CONFLICT (destination_id, locale) DO NOTHING''').bindparams(
            id=guide_id, source_id=source_id, slug=slug, overview=overview,
            highlights=__import__('json').dumps(highlights)))
        op.execute(sa.text('''INSERT INTO poi
            (id, destination_id, slug, category, content_status, source_id)
            SELECT CAST(:id AS UUID), d.id, :poi_slug, :category, 'sample', CAST(:source_id AS UUID)
            FROM destinations d WHERE d.slug = :slug
            ON CONFLICT (destination_id, slug) DO NOTHING''').bindparams(
            id=poi_id, slug=slug, poi_slug=poi_slug, category=category, source_id=source_id))
        op.execute(sa.text('''INSERT INTO poi_translations
            (id, poi_id, locale, title, description, local_tips)
            SELECT CAST(:id AS UUID), p.id, 'en', :title, :description, ''
            FROM poi p JOIN destinations d ON d.id = p.destination_id
            WHERE d.slug = :slug AND p.slug = :poi_slug
            ON CONFLICT (poi_id, locale) DO NOTHING''').bindparams(
            id=translated_poi_id, title=title, description=description, slug=slug, poi_slug=poi_slug))


def downgrade():
    op.drop_table('poi_translations')
    op.drop_table('poi')
    op.drop_table('destination_guides')
    # Source records are retained; other content may refer to the same source in the future.
