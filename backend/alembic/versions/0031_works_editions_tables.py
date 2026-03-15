"""Add works, editions, user_editions, loans and related tables.

Creates all new Works/Editions schema tables alongside the existing books
table (additive only — no data changes, no existing columns dropped).
Also adds nullable FK columns to existing tables for the transition period.

Revision ID: 0031
Revises: 0030
Create Date: 2026-03-15
"""

import sqlalchemy as sa
from alembic import op

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── New core tables ───────────────────────────────────────────────────────

    op.create_table(
        "works",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("uuid", sa.String(36), nullable=False, unique=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("subtitle", sa.String(255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("language", sa.String(10), nullable=True),
        sa.Column("original_language", sa.String(10), nullable=True),
        sa.Column("original_publication_year", sa.Integer(), nullable=True),
        sa.Column("characters", sa.Text(), nullable=True),
        sa.Column("places", sa.Text(), nullable=True),
        sa.Column("awards", sa.Text(), nullable=True),
        sa.Column("locked_fields", sa.Text(), nullable=True),
        sa.Column("esoteric_enabled", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_works_uuid", "works", ["uuid"], unique=True)
    op.create_index("ix_works_title", "works", ["title"])
    op.create_index("ix_works_created_at", "works", ["created_at"])

    op.create_table(
        "work_authors",
        sa.Column("work_id", sa.Integer(), sa.ForeignKey("works.id"), primary_key=True),
        sa.Column("author_id", sa.Integer(), sa.ForeignKey("authors.id"), primary_key=True),
    )

    op.create_table(
        "work_tags",
        sa.Column("work_id", sa.Integer(), sa.ForeignKey("works.id"), primary_key=True),
        sa.Column("tag_id", sa.Integer(), sa.ForeignKey("tags.id"), primary_key=True),
    )

    op.create_table(
        "work_series",
        sa.Column("work_id", sa.Integer(), sa.ForeignKey("works.id"), primary_key=True),
        sa.Column("series_id", sa.Integer(), sa.ForeignKey("series.id"), primary_key=True),
        sa.Column("position", sa.Float(), nullable=True),
        sa.Column("volume", sa.String(100), nullable=True),
        sa.Column("arc", sa.String(255), nullable=True),
    )

    op.create_table(
        "work_contributors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("work_id", sa.Integer(), sa.ForeignKey("works.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
    )
    op.create_index("ix_work_contributors_work_id", "work_contributors", ["work_id"])
    op.create_index("ix_work_contributors_role", "work_contributors", ["role"])

    op.create_table(
        "editions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("uuid", sa.String(36), nullable=False, unique=True),
        sa.Column("work_id", sa.Integer(), sa.ForeignKey("works.id"), nullable=True),  # nullable during backfill
        sa.Column("library_id", sa.Integer(), sa.ForeignKey("libraries.id"), nullable=False),
        sa.Column("isbn", sa.String(20), nullable=True),
        sa.Column("publisher", sa.String(255), nullable=True),
        sa.Column("published_date", sa.DateTime(), nullable=True),
        sa.Column("language", sa.String(10), nullable=True),
        sa.Column("format", sa.String(20), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("cover_hash", sa.String(64), nullable=True),
        sa.Column("cover_format", sa.String(10), nullable=True),
        sa.Column("locked_fields", sa.Text(), nullable=True),
        sa.Column("abs_item_id", sa.String(64), nullable=True),
        sa.Column("physical_copy", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_editions_uuid", "editions", ["uuid"], unique=True)
    op.create_index("ix_editions_work_id", "editions", ["work_id"])
    op.create_index("ix_editions_library_id", "editions", ["library_id"])
    op.create_index("ix_editions_isbn", "editions", ["isbn"])
    op.create_index("ix_editions_abs_item_id", "editions", ["abs_item_id"])
    op.create_index("ix_editions_created_at", "editions", ["created_at"])

    op.create_table(
        "edition_files",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("edition_id", sa.Integer(), sa.ForeignKey("editions.id"), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("format", sa.String(10), nullable=False),
        sa.Column("file_path", sa.String(512), nullable=False, unique=True),
        sa.Column("file_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_edition_files_edition_id", "edition_files", ["edition_id"])
    op.create_index("ix_edition_files_format", "edition_files", ["format"])

    op.create_table(
        "edition_contributors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("edition_id", sa.Integer(), sa.ForeignKey("editions.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
    )
    op.create_index("ix_edition_contributors_edition_id", "edition_contributors", ["edition_id"])

    op.create_table(
        "user_editions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("edition_id", sa.Integer(), sa.ForeignKey("editions.id"), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="want_to_read"),
        sa.Column("current_page", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_pages", sa.Integer(), nullable=True),
        sa.Column("percentage", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("review", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("last_opened", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "edition_id", name="uq_user_edition"),
    )
    op.create_index("ix_user_editions_user_id", "user_editions", ["user_id"])
    op.create_index("ix_user_editions_edition_id", "user_editions", ["edition_id"])

    op.create_table(
        "loans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("edition_id", sa.Integer(), sa.ForeignKey("editions.id"), nullable=False),
        sa.Column("loaned_to_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("loaned_to_name", sa.String(255), nullable=True),
        sa.Column("loaned_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("due_back", sa.DateTime(), nullable=True),
        sa.Column("returned_at", sa.DateTime(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_loans_edition_id", "loans", ["edition_id"])
    op.create_index("ix_loans_loaned_to_user_id", "loans", ["loaned_to_user_id"])

    # ── Nullable FK columns added to existing tables ──────────────────────────
    # These are all nullable so the app keeps working unchanged during the
    # transition. Migration 0032 backfills them; 0033 adds NOT NULL constraints.

    # NOTE: Inline sa.ForeignKey() is omitted from add_column calls below because
    # SQLite's batch_alter_table requires all FK constraints to be named, but
    # SQLite does not enforce FKs by default anyway. The ORM relationships handle
    # referential integrity at the application level.

    with op.batch_alter_table("books") as batch_op:
        batch_op.add_column(sa.Column("work_id", sa.Integer(), nullable=True))

    with op.batch_alter_table("kobo_book_states") as batch_op:
        batch_op.add_column(sa.Column("edition_id", sa.Integer(), nullable=True))

    with op.batch_alter_table("annotations") as batch_op:
        batch_op.add_column(sa.Column("edition_id", sa.Integer(), nullable=True))

    with op.batch_alter_table("marginalia") as batch_op:
        batch_op.add_column(sa.Column("edition_id", sa.Integer(), nullable=True))

    with op.batch_alter_table("shelf_books") as batch_op:
        batch_op.add_column(sa.Column("work_id", sa.Integer(), nullable=True))

    with op.batch_alter_table("collection_books") as batch_op:
        batch_op.add_column(sa.Column("work_id", sa.Integer(), nullable=True))

    with op.batch_alter_table("collections") as batch_op:
        batch_op.add_column(sa.Column("cover_work_id", sa.Integer(), nullable=True))

    with op.batch_alter_table("read_sessions") as batch_op:
        batch_op.add_column(sa.Column("work_id", sa.Integer(), nullable=True))

    with op.batch_alter_table("book_analyses") as batch_op:
        batch_op.add_column(sa.Column("work_id", sa.Integer(), nullable=True))

    with op.batch_alter_table("computational_analyses") as batch_op:
        batch_op.add_column(sa.Column("work_id", sa.Integer(), nullable=True))

    with op.batch_alter_table("book_prompt_configs") as batch_op:
        batch_op.add_column(sa.Column("work_id", sa.Integer(), nullable=True))

    # read_progress is handled separately — the whole table will be superseded
    # by user_editions, but we add edition_id for the transition
    with op.batch_alter_table("read_progress") as batch_op:
        batch_op.add_column(sa.Column("edition_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("read_progress") as batch_op:
        batch_op.drop_column("edition_id")
    with op.batch_alter_table("book_prompt_configs") as batch_op:
        batch_op.drop_column("work_id")
    with op.batch_alter_table("computational_analyses") as batch_op:
        batch_op.drop_column("work_id")
    with op.batch_alter_table("book_analyses") as batch_op:
        batch_op.drop_column("work_id")
    with op.batch_alter_table("read_sessions") as batch_op:
        batch_op.drop_column("work_id")
    with op.batch_alter_table("collections") as batch_op:
        batch_op.drop_column("cover_work_id")
    with op.batch_alter_table("collection_books") as batch_op:
        batch_op.drop_column("work_id")
    with op.batch_alter_table("shelf_books") as batch_op:
        batch_op.drop_column("work_id")
    with op.batch_alter_table("marginalia") as batch_op:
        batch_op.drop_column("edition_id")
    with op.batch_alter_table("annotations") as batch_op:
        batch_op.drop_column("edition_id")
    with op.batch_alter_table("kobo_book_states") as batch_op:
        batch_op.drop_column("edition_id")
    with op.batch_alter_table("books") as batch_op:
        batch_op.drop_column("work_id")

    op.drop_table("loans")
    op.drop_table("user_editions")
    op.drop_table("edition_contributors")
    op.drop_table("edition_files")
    op.drop_table("editions")
    op.drop_table("work_contributors")
    op.drop_table("work_series")
    op.drop_table("work_tags")
    op.drop_table("work_authors")
    op.drop_table("works")
