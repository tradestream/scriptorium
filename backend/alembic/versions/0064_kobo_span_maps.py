"""add kobo_span_maps table for real KoboSpan id round-tripping

Revision ID: 0064
Revises: 0063
"""
from alembic import op
import sqlalchemy as sa

revision = "0064"
down_revision = "0063"


def upgrade() -> None:
    op.create_table(
        "kobo_span_maps",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "edition_file_id",
            sa.Integer,
            sa.ForeignKey("edition_files.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("spine_index", sa.Integer, nullable=False),
        sa.Column("chapter_href", sa.String(512), nullable=False),
        sa.Column("span_ids", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "edition_file_id", "spine_index", name="uq_span_map_file_spine"
        ),
    )
    op.create_index(
        "ix_span_map_chapter",
        "kobo_span_maps",
        ["edition_file_id", "chapter_href"],
    )


def downgrade() -> None:
    op.drop_index("ix_span_map_chapter", table_name="kobo_span_maps")
    op.drop_table("kobo_span_maps")
