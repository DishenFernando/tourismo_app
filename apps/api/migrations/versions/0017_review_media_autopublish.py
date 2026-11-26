"""Allow up to five reviews per author/listing and add safe review image storage.

Revision ID: 0017_review_media
Revises: 0016_customer_reviews
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '0017_review_media'
down_revision = '0016_customer_reviews'
branch_labels = None
depends_on = None


def upgrade():
    # Existing review records are preserved; the old uniqueness constraint is removed.
    op.drop_constraint('uq_customer_review_author_listing', 'customer_reviews', type_='unique')
    op.create_index('ix_customer_reviews_listing_author', 'customer_reviews',
                    ['listing_id', 'author_id'])
    op.create_table('customer_review_images',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('review_id', UUID(as_uuid=True), sa.ForeignKey('customer_reviews.id', ondelete='CASCADE'), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('jpeg_data', sa.LargeBinary(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('review_id', 'position', name='uq_customer_review_image_position'),
        sa.CheckConstraint('position BETWEEN 0 AND 4', name='ck_customer_review_image_position'))
    op.create_index('ix_customer_review_images_review', 'customer_review_images', ['review_id'])


def downgrade():
    # Downgrade is intentionally guarded: any author with >1 review would be lost
    # or blocked by a uniqueness constraint. Archive/resolve data before downgrade.
    conn = op.get_bind()
    duplicates = conn.execute(sa.text('''
      SELECT 1 FROM customer_reviews GROUP BY listing_id, author_id HAVING COUNT(*) > 1 LIMIT 1
    ''')).first()
    if duplicates:
        raise RuntimeError('Cannot downgrade while any author has multiple reviews on a listing')
    op.drop_table('customer_review_images')
    op.drop_index('ix_customer_reviews_listing_author', table_name='customer_reviews')
    op.create_unique_constraint('uq_customer_review_author_listing', 'customer_reviews',
                                ['listing_id', 'author_id'])
