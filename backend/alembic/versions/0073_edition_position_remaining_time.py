"""edition_positions.remaining_time_minutes

Per the Kavita / Komga reading-state preservation pattern: keep the
device's own time-left estimate when it volunteers one (Kobo's
``Statistics.RemainingTimeMinutes``) so the web reader can read it
back instead of always re-deriving from a pace-of-reading model.

Revision ID: 0073
Revises: 0072
"""
import sqlalchemy as sa
from alembic import op


revision = "0073"
down_revision = "0072"


def upgrade() -> None:
    with op.batch_alter_table("edition_positions") as batch_op:
        batch_op.add_column(
            sa.Column("remaining_time_minutes", sa.Integer(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("edition_positions") as batch_op:
        batch_op.drop_column("remaining_time_minutes")
