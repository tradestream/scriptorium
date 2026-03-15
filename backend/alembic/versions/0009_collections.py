"""Add collections and collection_books tables.

Revision ID: 0009
Revises: 0008
Create Date: 2026-03-14
"""

from alembic import op
import sqlalchemy as sa

revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "collections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("cover_book_id", sa.Integer(), sa.ForeignKey("books.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_collections_user_id", "collections", ["user_id"])

    op.create_table(
        "collection_books",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("collection_id", sa.Integer(), sa.ForeignKey("collections.id"), nullable=False),
        sa.Column("book_id", sa.Integer(), sa.ForeignKey("books.id"), nullable=False),
        sa.Column("position", sa.Integer(), default=0, nullable=False, server_default="0"),
        sa.Column("added_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_collection_books_collection_id", "collection_books", ["collection_id"])
    op.create_index("ix_collection_books_book_id", "collection_books", ["book_id"])


def downgrade() -> None:
    op.drop_table("collection_books")
    op.drop_table("collections")
