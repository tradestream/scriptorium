"""Add location field to editions for physical book tracking.

Revision ID: 0040
Revises: 0039
Create Date: 2026-03-16
"""
from alembic import op
import sqlalchemy as sa

revision = "0040"
down_revision = "0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("editions", sa.Column("location", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("editions", "location")
