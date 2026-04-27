"""add cfi column to read_progress for web reader cursor restore

Revision ID: 0065
Revises: 0064
"""
from alembic import op
import sqlalchemy as sa

revision = "0065"
down_revision = "0064"


def upgrade() -> None:
    with op.batch_alter_table("read_progress") as batch_op:
        batch_op.add_column(sa.Column("cfi", sa.String(1024), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("read_progress") as batch_op:
        batch_op.drop_column("cfi")
