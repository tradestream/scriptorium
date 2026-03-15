"""phase3: koreader_progress table

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-13
"""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "koreader_progress",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False, index=True),
        # KOReader document key — typically MD5 of the filename
        sa.Column("document", sa.String(255), nullable=False, index=True),
        # Raw KOReader progress string (xpath or percentage)
        sa.Column("progress", sa.String(1024), nullable=False, default="0"),
        # Normalized percentage (0.0-1.0)
        sa.Column("percentage", sa.Float, nullable=False, default=0.0),
        sa.Column("device", sa.String(255), nullable=True),
        sa.Column("device_id", sa.String(255), nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint("user_id", "document", name="uq_koreader_user_document"),
    )


def downgrade():
    op.drop_table("koreader_progress")
