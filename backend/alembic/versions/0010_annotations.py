"""Add annotations table.

Revision ID: 0010
Revises: 0009
Create Date: 2026-03-14
"""

from alembic import op
import sqlalchemy as sa

revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "annotations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("book_id", sa.Integer(), sa.ForeignKey("books.id"), nullable=False),
        sa.Column("file_id", sa.Integer(), sa.ForeignKey("book_files.id"), nullable=True),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("location", sa.String(500), nullable=True),
        sa.Column("chapter", sa.String(255), nullable=True),
        sa.Column("color", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_annotations_user_id", "annotations", ["user_id"])
    op.create_index("ix_annotations_book_id", "annotations", ["book_id"])
    op.create_index("ix_annotations_type", "annotations", ["type"])


def downgrade() -> None:
    op.drop_table("annotations")
