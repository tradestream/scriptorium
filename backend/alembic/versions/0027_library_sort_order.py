"""Add sort_order to libraries for user-defined sidebar ordering

Revision ID: 0027
Revises: 0026
Create Date: 2026-03-15
"""

import sqlalchemy as sa
from alembic import op

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("libraries", sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"))
    # Initialise sort_order based on creation order (oldest = 0)
    conn = op.get_bind()
    conn.execute(sa.text("""
        UPDATE libraries
        SET sort_order = (
            SELECT COUNT(*) FROM libraries l2 WHERE l2.created_at < libraries.created_at
        )
    """))


def downgrade() -> None:
    op.drop_column("libraries", "sort_order")
