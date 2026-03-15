"""Add enrichment API key columns to system_settings

Revision ID: 0030
Revises: 0029
Create Date: 2026-03-15
"""

import sqlalchemy as sa
from alembic import op

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("system_settings") as batch_op:
        batch_op.add_column(sa.Column("hardcover_api_key", sa.String(500), nullable=True))
        batch_op.add_column(sa.Column("comicvine_api_key", sa.String(500), nullable=True))
        batch_op.add_column(sa.Column("google_books_api_key", sa.String(500), nullable=True))
        batch_op.add_column(sa.Column("isbndb_api_key", sa.String(500), nullable=True))
        batch_op.add_column(sa.Column("amazon_cookie", sa.Text, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("system_settings") as batch_op:
        batch_op.drop_column("amazon_cookie")
        batch_op.drop_column("isbndb_api_key")
        batch_op.drop_column("google_books_api_key")
        batch_op.drop_column("comicvine_api_key")
        batch_op.drop_column("hardcover_api_key")
