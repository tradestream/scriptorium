"""Add commentator and source fields to marginalia and annotations

Revision ID: 0020
Revises: 0019
Create Date: 2026-03-14
"""

import sqlalchemy as sa
from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("marginalia", sa.Column("commentator", sa.String(255), nullable=True))
    op.add_column("marginalia", sa.Column("source", sa.String(500), nullable=True))
    op.add_column("annotations", sa.Column("commentator", sa.String(255), nullable=True))
    op.add_column("annotations", sa.Column("source", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("marginalia", "commentator")
    op.drop_column("marginalia", "source")
    op.drop_column("annotations", "commentator")
    op.drop_column("annotations", "source")
