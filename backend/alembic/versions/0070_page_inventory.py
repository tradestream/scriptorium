"""edition_file_pages — per-page archive inventory cache

Avoids re-walking ZIP namelists on every comic page request. Populated
at ingest time for new books; existing CBZ files can be backfilled
lazily on first read or via a one-shot script.

Revision ID: 0070
Revises: 0069
"""
import sqlalchemy as sa
from alembic import op


revision = "0070"
down_revision = "0069"


def upgrade() -> None:
    op.create_table(
        "edition_file_pages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "edition_file_id",
            sa.Integer(),
            sa.ForeignKey("edition_files.id", ondelete="CASCADE"),
            index=True,
            nullable=False,
        ),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(1024), nullable=False),
        sa.Column("media_type", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.UniqueConstraint(
            "edition_file_id", "page_number", name="uq_edition_file_page_number"
        ),
    )
    op.create_index(
        "ix_edition_file_pages_file_page",
        "edition_file_pages",
        ["edition_file_id", "page_number"],
    )


def downgrade() -> None:
    op.drop_index("ix_edition_file_pages_file_page", table_name="edition_file_pages")
    op.drop_table("edition_file_pages")
