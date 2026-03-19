"""add sync_to_kobo and source to collections

Revision ID: 0054
Revises: 0053
"""
from alembic import op
import sqlalchemy as sa

revision = "0054"
down_revision = "0053"


def upgrade() -> None:
    with op.batch_alter_table("collections") as batch_op:
        batch_op.add_column(sa.Column("sync_to_kobo", sa.Boolean, server_default="0", nullable=False))
        batch_op.add_column(sa.Column("source", sa.String(20), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("collections") as batch_op:
        batch_op.drop_column("source")
        batch_op.drop_column("sync_to_kobo")
