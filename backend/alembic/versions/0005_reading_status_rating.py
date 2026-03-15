"""Add rating to read_progress and want_to_read status support.

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-14
"""

from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("read_progress") as batch_op:
        batch_op.add_column(sa.Column("rating", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("read_progress") as batch_op:
        batch_op.drop_column("rating")
