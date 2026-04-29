"""reading_lists + reading_list_entries

Adds first-class ordered reading lists, distinct from ``shelves`` (flat
bag) and ``collections`` (flat or smart-filtered). Pattern borrowed
from Kavita / Komga: a reading list is an ordered sequence with
next/previous semantics, used for arc reading, course curricula, and
"things I want to read this year in this order."

Revision ID: 0069
Revises: 0068
"""
import sqlalchemy as sa
from alembic import op


revision = "0069"
down_revision = "0068"


def upgrade() -> None:
    op.create_table(
        "reading_lists",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("cover_work_id", sa.Integer(), sa.ForeignKey("works.id"), nullable=True),
        sa.Column("source", sa.String(64), nullable=True),
        sa.Column("comicvine_id", sa.String(64), nullable=True),
        sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("sync_to_kobo", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
    )
    op.create_table(
        "reading_list_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "reading_list_id",
            sa.Integer(),
            sa.ForeignKey("reading_lists.id", ondelete="CASCADE"),
            index=True,
            nullable=False,
        ),
        sa.Column(
            "edition_id",
            sa.Integer(),
            sa.ForeignKey("editions.id", ondelete="CASCADE"),
            index=True,
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
    )
    op.create_index(
        "ix_reading_list_entries_list_position",
        "reading_list_entries",
        ["reading_list_id", "position"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_reading_list_entries_list_position",
        table_name="reading_list_entries",
    )
    op.drop_table("reading_list_entries")
    op.drop_table("reading_lists")
