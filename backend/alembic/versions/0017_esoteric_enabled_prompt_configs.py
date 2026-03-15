"""Add esoteric_enabled to books and book_prompt_configs table.

Revision ID: 0017
Revises: 0016
Create Date: 2026-03-14
"""

from alembic import op
import sqlalchemy as sa

revision = '0017'
down_revision = '0016'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('books', sa.Column('esoteric_enabled', sa.Boolean(), nullable=False, server_default='0'))
    op.create_table(
        'book_prompt_configs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('book_id', sa.Integer(), sa.ForeignKey('books.id'), nullable=False, index=True),
        sa.Column('template_id', sa.Integer(), sa.ForeignKey('analysis_templates.id'), nullable=True),
        sa.Column('custom_system_prompt', sa.Text(), nullable=True),
        sa.Column('custom_user_prompt', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint('book_id', 'template_id', name='uq_book_template_prompt'),
    )


def downgrade() -> None:
    op.drop_table('book_prompt_configs')
    op.drop_column('books', 'esoteric_enabled')
