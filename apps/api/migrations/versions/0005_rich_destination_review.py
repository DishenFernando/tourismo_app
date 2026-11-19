"""Phase 2.3: source-referenced UNESCO site centroids and POI coordinates.

Reference points describe heritage sites, NOT entrances, walking routes or
precise meeting points. All other destinations stay unlocated until sourced.
Existing photos, profiles, guides and trips are preserved.
"""
import uuid
from alembic import op
import sqlalchemy as sa

revision = '0005_rich_destination_review'
down_revision = '0004_catalog_admin_media'
branch_labels = None
depends_on = None

# Coordinates converted from DMS on the linked UNESCO World Heritage Centre pages.
# These are property reference locations, not navigation entrances.
UNESCO_SITES = (
    ('galle', 'old-town-galle-fort', 6.028051111, 80.216346111, 'https://whc.unesco.org/en/list/451/'),
    ('kandy', 'sacred-city-kandy', 7.293611111, 80.640277778, 'https://whc.unesco.org/en/list/450/'),
    ('anuradhapura', 'sacred-city-anuradhapura', 8.333333333, 80.383333333, 'https://whc.unesco.org/en/list/200/'),
    ('sigiriya', 'ancient-city-sigiriya', 7.95, 80.75, 'https://whc.unesco.org/en/list/202/'),
)


def uid(name):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, 'tourismo:phase23:' + name))


def upgrade():
    op.add_column('poi', sa.Column('latitude', sa.Float(), nullable=True))
    op.add_column('poi', sa.Column('longitude', sa.Float(), nullable=True))
    op.create_check_constraint('ck_poi_coordinates_pair', 'poi',
        '(latitude IS NULL AND longitude IS NULL) OR '
        '(latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180)')

    # One additional sample guide for an existing Phase 2.2 destination.
    op.execute(sa.text("""INSERT INTO content_sources (id, name, url, license_status)
        VALUES (CAST(:id AS UUID), 'UNESCO World Heritage Centre', :url, 'reference_link_only')
        ON CONFLICT (id) DO NOTHING""").bindparams(
        id=uid('sigiriya-source'), url='https://whc.unesco.org/en/list/202/'))
    op.execute(sa.text("""INSERT INTO destination_guides
        (id, destination_id, locale, overview, highlights, local_tips, content_status, source_id)
        SELECT CAST(:id AS UUID), d.id, 'en', :overview, CAST(:highlights AS jsonb),
               '[]'::jsonb, 'sample', CAST(:source_id AS UUID)
        FROM destinations d WHERE d.slug = 'sigiriya'
        ON CONFLICT (destination_id, locale) DO NOTHING""").bindparams(
        id=uid('sigiriya-guide'), source_id=uid('sigiriya-source'),
        overview='The Ancient City of Sigiriya is a UNESCO World Heritage archaeological site in Sri Lanka, celebrated for its historic rock citadel and cultural landscape. The point on this guide is a UNESCO site reference, not an entrance.',
        highlights='["UNESCO World Heritage archaeological site", "Historic rock citadel and cultural landscape"]'))
    op.execute(sa.text("""INSERT INTO poi (id, destination_id, slug, category, content_status, source_id)
        SELECT CAST(:id AS UUID), d.id, 'ancient-city-sigiriya', 'heritage', 'sample',
               CAST(:source_id AS UUID) FROM destinations d WHERE d.slug = 'sigiriya'
        ON CONFLICT (destination_id, slug) DO NOTHING""").bindparams(
        id=uid('sigiriya-poi'), source_id=uid('sigiriya-source')))
    op.execute(sa.text("""INSERT INTO poi_translations (id, poi_id, locale, title, description, local_tips)
        SELECT CAST(:id AS UUID), p.id, 'en', 'Ancient City of Sigiriya', :description, ''
        FROM poi p JOIN destinations d ON d.id = p.destination_id
        WHERE d.slug = 'sigiriya' AND p.slug = 'ancient-city-sigiriya'
        ON CONFLICT (poi_id, locale) DO NOTHING""").bindparams(
        id=uid('sigiriya-translation'),
        description='UNESCO-listed ancient city and rock citadel. The site reference point is not an entrance or route.'))

    for destination_slug, poi_slug, latitude, longitude, _ in UNESCO_SITES:
        op.execute(sa.text("""UPDATE poi SET latitude=:latitude, longitude=:longitude,
            location=ST_SetSRID(ST_MakePoint(:longitude, :latitude),4326)::geography
            WHERE destination_id=(SELECT id FROM destinations WHERE slug=:destination_slug)
              AND slug=:poi_slug AND content_status='sample'
              AND latitude IS NULL AND longitude IS NULL AND location IS NULL""").bindparams(
            latitude=latitude, longitude=longitude,
            destination_slug=destination_slug, poi_slug=poi_slug))


def downgrade():
    op.drop_constraint('ck_poi_coordinates_pair', 'poi', type_='check')
    op.drop_column('poi', 'longitude')
    op.drop_column('poi', 'latitude')
    # Do not delete seeded content: an editor might have extended it.
