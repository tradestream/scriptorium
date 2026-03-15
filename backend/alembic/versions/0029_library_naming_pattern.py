"""Add system_settings table and library naming_pattern column

Revision ID: 0029
Revises: 0028
Create Date: 2026-03-15
"""

import sqlalchemy as sa
from alembic import op

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create system_settings single-row table
    op.create_table(
        "system_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("naming_enabled", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column(
            "naming_pattern",
            sa.String(500),
            nullable=False,
            server_default="{authors}/{title}",
        ),
    )

    # Add per-library naming pattern override column
    with op.batch_alter_table("libraries") as batch_op:
        batch_op.add_column(
            sa.Column("naming_pattern", sa.String(500), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("libraries") as batch_op:
        batch_op.drop_column("naming_pattern")

    op.drop_table("system_settings")
