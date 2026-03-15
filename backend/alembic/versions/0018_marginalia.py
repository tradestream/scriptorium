"""Add marginalia table

Revision ID: 0018
Revises: 0017
Create Date: 2026-03-14
"""

import sqlalchemy as sa
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "marginalia",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("book_id", sa.Integer(), sa.ForeignKey("books.id"), nullable=False, index=True),
        sa.Column("file_id", sa.Integer(), sa.ForeignKey("book_files.id"), nullable=True),
        sa.Column("kind", sa.String(30), nullable=False, server_default="observation", index=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("location", sa.String(500), nullable=True),
        sa.Column("chapter", sa.String(255), nullable=True),
        sa.Column("related_refs", sa.Text(), nullable=True),
        sa.Column("tags", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("marginalia")
