"""Add abs_item_id to books table for AudiobookShelf linking.

Revision ID: 0025
Revises: 0024
Create Date: 2026-03-14
"""

from alembic import op
import sqlalchemy as sa


revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def _column_exists(conn, table, column):
    r = conn.execute(sa.text(f"PRAGMA table_info({table})"))
    return any(row[1] == column for row in r.fetchall())


def upgrade():
    conn = op.get_bind()
    if not _column_exists(conn, "books", "abs_item_id"):
        op.add_column("books", sa.Column("abs_item_id", sa.String(64), nullable=True))
        op.create_index("ix_books_abs_item_id", "books", ["abs_item_id"])


def downgrade():
    op.drop_index("ix_books_abs_item_id", table_name="books")
    op.drop_column("books", "abs_item_id")
