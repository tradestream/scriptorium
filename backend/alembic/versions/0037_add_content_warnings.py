"""Add content_warnings to works table.

Revision ID: 0037
Revises: 0036
Create Date: 2026-03-15
"""
from alembic import op
import sqlalchemy as sa

revision = "0037"
down_revision = "0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("works", sa.Column("content_warnings", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("works", "content_warnings")
