"""phase2: ingest_logs + smart shelves

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-13
"""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    # ingest_logs table
    op.create_table(
        "ingest_logs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("book_id", sa.Integer, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    # smart shelf columns
    op.add_column("shelves", sa.Column("is_smart", sa.Boolean, nullable=False, server_default="0"))
    op.add_column("shelves", sa.Column("smart_filter", sa.Text, nullable=True))


def downgrade():
    op.drop_table("ingest_logs")
    op.drop_column("shelves", "is_smart")
    op.drop_column("shelves", "smart_filter")
