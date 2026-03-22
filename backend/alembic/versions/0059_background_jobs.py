"""background_jobs table for multi-worker job tracking

Revision ID: 0059
Revises: 0058
"""
from alembic import op
import sqlalchemy as sa

revision = "0059"
down_revision = "0058"


def upgrade() -> None:
    op.create_table(
        "background_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_type", sa.String(50), nullable=False, index=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("total", sa.Integer, nullable=False, server_default="0"),
        sa.Column("done", sa.Integer, nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("current", sa.String(500), nullable=True),
        sa.Column("started_at", sa.String(50), nullable=True),
        sa.Column("counters", sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_table("background_jobs")
