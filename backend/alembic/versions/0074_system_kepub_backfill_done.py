"""system_settings.kepub_backfill_done

Tracks whether the one-shot KEPUB pre-conversion backfill has run, so
the startup auto-kick fires exactly once instead of on every restart.

Revision ID: 0074
Revises: 0073
"""
import sqlalchemy as sa
from alembic import op


revision = "0074"
down_revision = "0073"


def upgrade() -> None:
    with op.batch_alter_table("system_settings") as batch_op:
        batch_op.add_column(
            sa.Column(
                "kepub_backfill_done",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("system_settings") as batch_op:
        batch_op.drop_column("kepub_backfill_done")
