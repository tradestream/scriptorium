"""Add external provider IDs and community ratings to works.

Revision ID: 0048
Revises: 0047
Create Date: 2026-03-17
"""
from alembic import op
import sqlalchemy as sa

revision = "0048"
down_revision = "0047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # External provider IDs
    op.add_column("works", sa.Column("goodreads_id", sa.String(20), nullable=True))
    op.add_column("works", sa.Column("google_id", sa.String(20), nullable=True))
    op.add_column("works", sa.Column("hardcover_id", sa.String(50), nullable=True))
    op.create_index("ix_works_goodreads_id", "works", ["goodreads_id"])
    op.create_index("ix_works_google_id", "works", ["google_id"])
    op.create_index("ix_works_hardcover_id", "works", ["hardcover_id"])
    # Community ratings
    op.add_column("works", sa.Column("goodreads_rating", sa.Float, nullable=True))
    op.add_column("works", sa.Column("goodreads_rating_count", sa.Integer, nullable=True))
    op.add_column("works", sa.Column("amazon_rating", sa.Float, nullable=True))
    op.add_column("works", sa.Column("amazon_rating_count", sa.Integer, nullable=True))


def downgrade() -> None:
    op.drop_column("works", "amazon_rating_count")
    op.drop_column("works", "amazon_rating")
    op.drop_column("works", "goodreads_rating_count")
    op.drop_column("works", "goodreads_rating")
    op.drop_index("ix_works_hardcover_id", table_name="works")
    op.drop_index("ix_works_google_id", table_name="works")
    op.drop_index("ix_works_goodreads_id", table_name="works")
    op.drop_column("works", "hardcover_id")
    op.drop_column("works", "google_id")
    op.drop_column("works", "goodreads_id")
