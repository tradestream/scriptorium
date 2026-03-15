"""Add library_access table for per-user library permissions.

Revision ID: 0011
Revises: 0010
Create Date: 2026-03-14
"""

from alembic import op
import sqlalchemy as sa

revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "library_access",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("library_id", sa.Integer(), sa.ForeignKey("libraries.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("access_level", sa.String(20), nullable=False, server_default="read"),
        sa.Column("granted_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_library_access_library_id", "library_access", ["library_id"])
    op.create_index("ix_library_access_user_id", "library_access", ["user_id"])


def downgrade() -> None:
    op.drop_table("library_access")
