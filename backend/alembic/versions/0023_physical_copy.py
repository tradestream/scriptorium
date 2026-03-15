"""Add physical_copy flag to books

Revision ID: 0023
Revises: 0022
Create Date: 2026-03-14
"""

import sqlalchemy as sa
from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def _has_column(conn, table: str, column: str) -> bool:
    rows = conn.execute(sa.text(f"PRAGMA table_info({table})")).fetchall()
    return any(row[1] == column for row in rows)


def upgrade() -> None:
    conn = op.get_bind()
    if not _has_column(conn, "books", "physical_copy"):
        op.add_column(
            "books",
            sa.Column(
                "physical_copy",
                sa.Boolean(),
                nullable=False,
                server_default="0",
            ),
        )


def downgrade() -> None:
    # SQLite doesn't support DROP COLUMN natively before 3.35 — skip
    pass
