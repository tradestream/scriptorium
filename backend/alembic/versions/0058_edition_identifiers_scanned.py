"""add identifiers_scanned flag to editions

Revision ID: 0058
Revises: 0057
"""
from alembic import op
import sqlalchemy as sa

revision = "0058"
down_revision = "0057"


def upgrade() -> None:
    with op.batch_alter_table("editions") as batch_op:
        batch_op.add_column(
            sa.Column("identifiers_scanned", sa.Boolean, nullable=False, server_default="0")
        )


def downgrade() -> None:
    with op.batch_alter_table("editions") as batch_op:
        batch_op.drop_column("identifiers_scanned")
