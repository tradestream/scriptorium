"""Add binding, condition, purchase fields to editions.

Revision ID: 0042
Revises: 0041
Create Date: 2026-03-16
"""
from alembic import op
import sqlalchemy as sa

revision = "0042"
down_revision = "0041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("editions", sa.Column("binding", sa.String(50), nullable=True))
    op.add_column("editions", sa.Column("condition", sa.String(20), nullable=True))
    op.add_column("editions", sa.Column("purchase_price", sa.Float, nullable=True))
    op.add_column("editions", sa.Column("purchase_date", sa.DateTime, nullable=True))
    op.add_column("editions", sa.Column("purchase_from", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("editions", "purchase_from")
    op.drop_column("editions", "purchase_date")
    op.drop_column("editions", "purchase_price")
    op.drop_column("editions", "condition")
    op.drop_column("editions", "binding")
