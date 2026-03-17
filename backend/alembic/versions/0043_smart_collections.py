"""Add smart collection support (is_smart + smart_filter) to collections.

Revision ID: 0043
Revises: 0042
Create Date: 2026-03-16
"""
from alembic import op
import sqlalchemy as sa

revision = "0043"
down_revision = "0042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("collections", sa.Column("is_smart", sa.Boolean, server_default="0", nullable=False))
    op.add_column("collections", sa.Column("smart_filter", sa.Text, nullable=True))


def downgrade() -> None:
    op.drop_column("collections", "smart_filter")
    op.drop_column("collections", "is_smart")
