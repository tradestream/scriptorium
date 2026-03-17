"""Add ASIN field to editions table.

Revision ID: 0039
Revises: 0038
Create Date: 2026-03-16
"""
from alembic import op
import sqlalchemy as sa

revision = "0039"
down_revision = "0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("editions", sa.Column("asin", sa.String(10), nullable=True))
    op.create_index("ix_editions_asin", "editions", ["asin"])


def downgrade() -> None:
    op.drop_index("ix_editions_asin", table_name="editions")
    op.drop_column("editions", "asin")
