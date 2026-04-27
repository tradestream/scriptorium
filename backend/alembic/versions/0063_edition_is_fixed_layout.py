"""add is_fixed_layout flag to editions

Revision ID: 0063
Revises: 0062
"""
from alembic import op
import sqlalchemy as sa

revision = "0063"
down_revision = "0062"


def upgrade() -> None:
    with op.batch_alter_table("editions") as batch_op:
        batch_op.add_column(
            sa.Column("is_fixed_layout", sa.Boolean, nullable=False, server_default="0")
        )


def downgrade() -> None:
    with op.batch_alter_table("editions") as batch_op:
        batch_op.drop_column("is_fixed_layout")
