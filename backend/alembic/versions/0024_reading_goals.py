"""Add reading_goals table.

Revision ID: 0024
Revises: 0023
Create Date: 2026-03-14
"""

from alembic import op
import sqlalchemy as sa


revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def _table_exists(conn, name):
    r = conn.execute(
        sa.text("SELECT name FROM sqlite_master WHERE type='table' AND name=:n"),
        {"n": name},
    )
    return r.fetchone() is not None


def upgrade():
    conn = op.get_bind()
    if not _table_exists(conn, "reading_goals"):
        op.create_table(
            "reading_goals",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("year", sa.Integer(), nullable=False),
            sa.Column("target_books", sa.Integer(), nullable=False, server_default="12"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("user_id", "year", name="uq_reading_goal_user_year"),
        )


def downgrade():
    op.drop_table("reading_goals")
