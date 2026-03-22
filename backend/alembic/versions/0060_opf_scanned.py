"""add opf_scanned flag to editions

Revision ID: 0060
Revises: 0059
"""
from alembic import op
import sqlalchemy as sa

revision = "0060"
down_revision = "0059"


def upgrade() -> None:
    with op.batch_alter_table("editions") as batch_op:
        batch_op.add_column(
            sa.Column("opf_scanned", sa.Boolean, nullable=False, server_default="0")
        )


def downgrade() -> None:
    with op.batch_alter_table("editions") as batch_op:
        batch_op.drop_column("opf_scanned")
