"""rename work_id to edition_id in computational_analyses

Revision ID: 0062
Revises: 0061
"""
from alembic import op
import sqlalchemy as sa

revision = "0062"
down_revision = "0061"


def upgrade() -> None:
    with op.batch_alter_table("computational_analyses") as batch_op:
        batch_op.alter_column("work_id", new_column_name="edition_id")


def downgrade() -> None:
    with op.batch_alter_table("computational_analyses") as batch_op:
        batch_op.alter_column("edition_id", new_column_name="work_id")
