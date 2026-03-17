"""Add reading level fields to works table.

Revision ID: 0045
Revises: 0044
Create Date: 2026-03-16
"""
from alembic import op
import sqlalchemy as sa

revision = "0045"
down_revision = "0044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("works", sa.Column("lexile", sa.Integer, nullable=True))
    op.add_column("works", sa.Column("lexile_code", sa.String(5), nullable=True))
    op.add_column("works", sa.Column("ar_level", sa.Float, nullable=True))
    op.add_column("works", sa.Column("ar_points", sa.Float, nullable=True))
    op.add_column("works", sa.Column("flesch_kincaid_grade", sa.Float, nullable=True))
    op.add_column("works", sa.Column("age_range", sa.String(50), nullable=True))
    op.add_column("works", sa.Column("interest_level", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("works", "interest_level")
    op.drop_column("works", "age_range")
    op.drop_column("works", "flesch_kincaid_grade")
    op.drop_column("works", "ar_points")
    op.drop_column("works", "ar_level")
    op.drop_column("works", "lexile_code")
    op.drop_column("works", "lexile")
