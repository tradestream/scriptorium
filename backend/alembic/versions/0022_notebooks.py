"""Add notebooks and notebook_entries tables

Revision ID: 0022
Revises: 0021
Create Date: 2026-03-14
"""

import sqlalchemy as sa
from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def _has_table(conn, table: str) -> bool:
    rows = conn.execute(
        sa.text("SELECT name FROM sqlite_master WHERE type='table' AND name=:t"),
        {"t": table},
    ).fetchall()
    return bool(rows)


def upgrade() -> None:
    conn = op.get_bind()

    if not _has_table(conn, "notebooks"):
        op.create_table(
            "notebooks",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False, index=True),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("description", sa.Text, nullable=True),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        )

    if not _has_table(conn, "notebook_entries"):
        op.create_table(
            "notebook_entries",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column(
                "notebook_id", sa.Integer, sa.ForeignKey("notebooks.id"), nullable=False, index=True
            ),
            sa.Column(
                "marginalium_id",
                sa.Integer,
                sa.ForeignKey("marginalia.id"),
                nullable=False,
                index=True,
            ),
            sa.Column("note", sa.Text, nullable=True),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
            sa.UniqueConstraint("notebook_id", "marginalium_id", name="uq_notebook_marginalium"),
        )


def downgrade() -> None:
    op.drop_table("notebook_entries")
    op.drop_table("notebooks")
