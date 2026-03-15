"""Add kobo_token_shelves junction table for per-shelf Kobo sync filtering.

When a token has shelf entries, only books from those shelves sync to the
device. Multiple shelves can be attached to one token (union, not intersection).
When no shelves are attached, all books from visible libraries sync (default).

Revision ID: 0014
Revises: 0013
Create Date: 2026-03-14
"""

from alembic import op
import sqlalchemy as sa

revision = '0014'
down_revision = '0013'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "kobo_token_shelves",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("token_id", sa.Integer(), sa.ForeignKey("kobo_sync_tokens.id"), nullable=False),
        sa.Column("shelf_id", sa.Integer(), sa.ForeignKey("shelves.id"), nullable=False),
    )
    op.create_index("ix_kobo_token_shelves_token_id", "kobo_token_shelves", ["token_id"])
    op.create_index("ix_kobo_token_shelves_shelf_id", "kobo_token_shelves", ["shelf_id"])


def downgrade() -> None:
    op.drop_table("kobo_token_shelves")
