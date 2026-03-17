"""Add display_name to users and backfill existing users.

Revision ID: 0044
Revises: 0043
Create Date: 2026-03-16
"""
from alembic import op
import sqlalchemy as sa

revision = "0044"
down_revision = "0043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("display_name", sa.String(255), nullable=True))

    # Backfill known users
    conn = op.get_bind()
    conn.execute(sa.text("UPDATE users SET display_name = 'Nathaniel Cochran' WHERE username = 'nathaniel'"))
    conn.execute(sa.text("UPDATE users SET display_name = 'Lisa Cochran' WHERE username = 'lisa'"))
    conn.execute(sa.text("UPDATE users SET display_name = 'Winston Cochran' WHERE username = 'winston'"))


def downgrade() -> None:
    op.drop_column("users", "display_name")
