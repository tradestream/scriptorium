"""Add librarything_api_key to system_settings.

Revision ID: 0035
Revises: 0034
Create Date: 2026-03-15
"""
from alembic import op
import sqlalchemy as sa

revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "system_settings",
        sa.Column("librarything_api_key", sa.String(500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("system_settings", "librarything_api_key")
