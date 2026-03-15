"""Add reading_level to marginalia

Revision ID: 0021
Revises: 0020
Create Date: 2026-03-14
"""

import sqlalchemy as sa
from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def _has_column(conn, table: str, column: str) -> bool:
    rows = conn.execute(sa.text(f"PRAGMA table_info({table})")).fetchall()
    return any(r[1] == column for r in rows)


def upgrade() -> None:
    conn = op.get_bind()
    if not _has_column(conn, "marginalia", "reading_level"):
        op.add_column(
            "marginalia",
            sa.Column("reading_level", sa.String(20), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("marginalia", "reading_level")
