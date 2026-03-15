"""Add reading_lists and reading_list_books tables.

Revision ID: 0008
Revises: 0007
Create Date: 2026-03-14
"""

from alembic import op
import sqlalchemy as sa

revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reading_lists",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_reading_lists_user_id", "reading_lists", ["user_id"])

    op.create_table(
        "reading_list_books",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("list_id", sa.Integer(), sa.ForeignKey("reading_lists.id"), nullable=False),
        sa.Column("book_id", sa.Integer(), sa.ForeignKey("books.id"), nullable=False),
        sa.Column("position", sa.Integer(), default=0, nullable=False, server_default="0"),
        sa.Column("added_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_reading_list_books_list_id", "reading_list_books", ["list_id"])
    op.create_index("ix_reading_list_books_book_id", "reading_list_books", ["book_id"])


def downgrade() -> None:
    op.drop_table("reading_list_books")
    op.drop_table("reading_lists")
