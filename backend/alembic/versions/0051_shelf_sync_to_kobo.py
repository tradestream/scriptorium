"""add sync_to_kobo flag on shelves

Revision ID: 0051
Revises: 0050
"""
from alembic import op
import sqlalchemy as sa

revision = "0051"
down_revision = "0050"


def upgrade() -> None:
    with op.batch_alter_table("shelves") as batch_op:
        batch_op.add_column(sa.Column("sync_to_kobo", sa.Boolean, server_default="0", nullable=False))

    # Auto-flag any shelf named "Kobo" as sync_to_kobo
    op.execute("UPDATE shelves SET sync_to_kobo = 1 WHERE LOWER(name) = 'kobo'")


def downgrade() -> None:
    with op.batch_alter_table("shelves") as batch_op:
        batch_op.drop_column("sync_to_kobo")
