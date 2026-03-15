"""Add OIDC fields to users table.

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-13
"""

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("oidc_subject", sa.String(512), nullable=True))
        batch_op.add_column(sa.Column("oidc_provider", sa.String(100), nullable=True))
        batch_op.create_index("ix_users_oidc_subject", ["oidc_subject"], unique=True)

    # Allow empty hashed_password for OIDC-only accounts
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("hashed_password", existing_type=sa.String(255), server_default="")


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_index("ix_users_oidc_subject")
        batch_op.drop_column("oidc_provider")
        batch_op.drop_column("oidc_subject")
