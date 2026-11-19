"""Phase 2.2: expanded destination directory, licensed photo records and admin roles.
Never updates a human-edited destination, profile, or trip; seeds sample entries only.
Revision ID: 0004_catalog_admin_media; Revises: 0003_destination_intelligence.
"""
import uuid
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from tourismo.geography.catalog_data import PLACES, COMMONS_PHOTOS

revision = '0004_catalog_admin_media'
down_revision = '0003_destination_intelligence'
branch_labels = None
depends_on = None


def _id(name):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, 'tourismo:phase22:' + name))


def upgrade():
    op.create_table('destination_photos',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('destination_id', UUID(as_uuid=True), sa.ForeignKey('destinations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('image_url', sa.String(2048), nullable=False),
        sa.Column('file_page_url', sa.String(2048), nullable=False),
        sa.Column('photographer', sa.String(160), nullable=False),
        sa.Column('license_name', sa.String(60), nullable=False),
        sa.Column('license_url', sa.String(512), nullable=False),
        sa.Column('alt_text', sa.String(240), nullable=False),
        sa.Column('is_primary', sa.Boolean, nullable=False, server_default=sa.true()),
        sa.UniqueConstraint('destination_id', 'file_page_url', name='uq_destination_photo_file'))
    op.create_index('ix_destination_photos_destination_id', 'destination_photos', ['destination_id'])
    for role, description in [('admin', 'Platform administrator with publishing privileges'),
                              ('editor', 'Editorial author: can create and edit drafts')]:
        op.execute(sa.text("""INSERT INTO platform_roles (id, key, description)
             VALUES (CAST(:id AS UUID), :role, :description) ON CONFLICT (key) DO NOTHING""").bindparams(
             id=_id('role:'+role),role=role,description=description))
    for slug, name, district, province in PLACES:
        op.execute(sa.text("""INSERT INTO destinations (id, slug, district, province, content_status)
            VALUES (CAST(:id AS UUID), :slug, :district, :province, 'sample')
            ON CONFLICT (slug) DO NOTHING""").bindparams(id=_id('destination:'+slug), slug=slug,
                district=district, province=province))
        op.execute(sa.text("""INSERT INTO destination_translations (id, destination_id, locale, title, summary)
            SELECT CAST(:id AS UUID), d.id, 'en', :title, :summary FROM destinations d
            WHERE d.slug=:slug ON CONFLICT (destination_id, locale) DO NOTHING""").bindparams(
                id=_id('translation:'+slug), slug=slug, title=name,
                summary=f'Explore {name} in {district} District, {province} Province. Detailed travel information is under editorial review.'))
    for slug, filename, photographer, license_name in COMMONS_PHOTOS:
        base = 'https://commons.wikimedia.org/wiki/'
        link = base + 'File:' + filename
        image = base + 'Special:FilePath/' + filename + '?width=1280'
        license_url = ('https://creativecommons.org/licenses/by-sa/3.0/' if license_name.endswith('3.0')
                       else 'https://creativecommons.org/licenses/by-sa/4.0/')
        op.execute(sa.text("""INSERT INTO destination_photos (id, destination_id, image_url,
            file_page_url, photographer, license_name, license_url, alt_text, is_primary)
            SELECT CAST(:id AS UUID), d.id, :image_url, :link, :photographer,
                   :license_name, :license_url, :alt_text, TRUE
            FROM destinations d WHERE d.slug=:slug
            ON CONFLICT (destination_id, file_page_url) DO NOTHING""").bindparams(
            id=_id('photo:'+slug),slug=slug,image_url=image,link=link,
            photographer=photographer,license_name=license_name,license_url=license_url,
            alt_text=f'Photograph of {slug.replace("-", " ")} in Sri Lanka'))


def downgrade():
    op.drop_table('destination_photos')
    # Do not delete seeded destinations or role assignments: users may now reference them.
