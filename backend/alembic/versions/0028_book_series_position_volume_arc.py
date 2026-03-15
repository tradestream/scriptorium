"""Add position, volume, arc to book_series association table

Revision ID: 0028
Revises: 0027
Create Date: 2026-03-15
"""

import sqlalchemy as sa
from alembic import op

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("book_series", sa.Column("position", sa.Float(), nullable=True))
    op.add_column("book_series", sa.Column("volume", sa.String(100), nullable=True))
    op.add_column("book_series", sa.Column("arc", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("book_series", "arc")
    op.drop_column("book_series", "volume")
    op.drop_column("book_series", "position")
