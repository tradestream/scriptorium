"""Add doi field to works table.

Revision ID: 0036
Revises: 0035
Create Date: 2026-03-15
"""
from alembic import op
import sqlalchemy as sa

revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "works",
        sa.Column("doi", sa.String(255), nullable=True),
    )
    op.create_index("ix_works_doi", "works", ["doi"])


def downgrade() -> None:
    op.drop_index("ix_works_doi", "works")
    op.drop_column("works", "doi")
