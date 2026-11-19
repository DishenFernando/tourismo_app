"""Deepen five EN sample destination guides with individually sourced POIs.

Revision ID: 0007_pilot_destination_guides
Revises: 0006_editorial_quality

Safe seed strategy: never overwrite published/draft/submitted guides, changed
sample guide text, or any guide with editor revisions. The migration does not
promote any sample content to 'published'. POIs are inserts-only, with no
unverified coordinates, hours, ticket prices, or photos.
"""
import json
import uuid
from alembic import op
import sqlalchemy as sa
from tourismo.geography.pilot_content import SOURCES, GUIDES, POIS

revision = '0007_pilot_destination_guides'
down_revision = '0006_editorial_quality'
branch_labels = None
depends_on = None


def stable_id(kind: str, key: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f'tourismo:phase25:{kind}:{key}'))


def upgrade():
    for source_key, (name, url) in SOURCES.items():
        op.execute(sa.text("""INSERT INTO content_sources (id, name, url, license_status)
            VALUES (CAST(:id AS UUID), :name, :url, 'reference_link_only')
            ON CONFLICT (id) DO NOTHING""").bindparams(
            id=stable_id('source', source_key), name=name, url=url))

    for slug, guide in GUIDES.items():
        op.execute(sa.text("""UPDATE destination_guides g
            SET overview=:overview,
                highlights=CAST(:highlights AS jsonb),
                local_tips=CAST(:local_tips AS jsonb),
                source_id=CAST(:source_id AS UUID)
            FROM destinations d
            WHERE g.destination_id=d.id AND d.slug=:slug
              AND g.locale='en' AND g.content_status='sample'
              AND g.overview=:original_overview
              AND NOT EXISTS (
                  SELECT 1 FROM destination_guide_revisions r WHERE r.guide_id=g.id
              )""").bindparams(
            slug=slug, source_id=stable_id('source', guide['source']),
            original_overview=guide['original_overview'],
            overview=guide['overview'],
            highlights=json.dumps(guide['highlights']),
            local_tips=json.dumps(guide['local_tips'])))

    for slug, poi_slug, title, category, source_key, description, local_tips in POIS:
        op.execute(sa.text("""INSERT INTO poi
            (id, destination_id, slug, category, content_status, source_id)
            SELECT CAST(:id AS UUID), d.id, :poi_slug, :category,
                   CASE WHEN d.content_status='published' THEN 'draft' ELSE 'sample' END,
                   CAST(:source_id AS UUID)
            FROM destinations d WHERE d.slug=:slug
            ON CONFLICT (destination_id, slug) DO NOTHING""").bindparams(
            id=stable_id('poi', f'{slug}:{poi_slug}'), slug=slug, poi_slug=poi_slug,
            category=category, source_id=stable_id('source', source_key)))
        op.execute(sa.text("""INSERT INTO poi_translations
            (id, poi_id, locale, title, description, local_tips)
            SELECT CAST(:id AS UUID), p.id, 'en', :title, :description, :local_tips
            FROM poi p JOIN destinations d ON d.id=p.destination_id
            WHERE d.slug=:slug AND p.slug=:poi_slug AND p.content_status IN ('sample', 'draft')
            ON CONFLICT (poi_id, locale) DO NOTHING""").bindparams(
            id=stable_id('poi-translation', f'{slug}:{poi_slug}:en'),
            slug=slug, poi_slug=poi_slug, title=title,
            description=description, local_tips=local_tips))


def downgrade():
    # Preserve published/edited/user-contributed content. Retaining additive
    # sample seeds is safer than deleting content possibly referenced by trips.
    pass
