"""Add locked_fields to books table.

Revision ID: 0015
Revises: 0014
Create Date: 2026-03-14
"""

from alembic import op
import sqlalchemy as sa

revision = '0015'
down_revision = '0014'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('books', sa.Column('locked_fields', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('books', 'locked_fields')
