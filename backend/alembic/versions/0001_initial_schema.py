"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-03-13

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("username", sa.String(100), nullable=False, unique=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("is_admin", sa.Boolean, nullable=False, default=False),
        sa.Column("is_active", sa.Boolean, nullable=False, default=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_users_username", "users", ["username"])
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_is_admin", "users", ["is_admin"])
    op.create_index("ix_users_is_active", "users", ["is_active"])

    op.create_table(
        "libraries",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("path", sa.String(512), nullable=False, unique=True),
        sa.Column("is_active", sa.Boolean, nullable=False, default=True),
        sa.Column("is_hidden", sa.Boolean, nullable=False, default=False),
        sa.Column("last_scanned", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_libraries_name", "libraries", ["name"])
    op.create_index("ix_libraries_is_active", "libraries", ["is_active"])
    op.create_index("ix_libraries_is_hidden", "libraries", ["is_hidden"])

    op.create_table(
        "authors",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("description", sa.Text, nullable=True),
    )
    op.create_index("ix_authors_name", "authors", ["name"])

    op.create_table(
        "tags",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
    )
    op.create_index("ix_tags_name", "tags", ["name"])

    op.create_table(
        "series",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("description", sa.Text, nullable=True),
    )
    op.create_index("ix_series_name", "series", ["name"])

    op.create_table(
        "books",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("uuid", sa.String(36), nullable=False, unique=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("isbn", sa.String(20), nullable=True),
        sa.Column("language", sa.String(10), nullable=True),
        sa.Column("published_date", sa.DateTime, nullable=True),
        sa.Column("cover_hash", sa.String(64), nullable=True),
        sa.Column("cover_format", sa.String(10), nullable=True),
        sa.Column("library_id", sa.Integer, sa.ForeignKey("libraries.id"), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_books_uuid", "books", ["uuid"])
    op.create_index("ix_books_title", "books", ["title"])
    op.create_index("ix_books_isbn", "books", ["isbn"])
    op.create_index("ix_books_created_at", "books", ["created_at"])

    op.create_table(
        "book_files",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("book_id", sa.Integer, sa.ForeignKey("books.id"), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("format", sa.String(10), nullable=False),
        sa.Column("file_path", sa.String(512), nullable=False, unique=True),
        sa.Column("file_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("file_size", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_book_files_format", "book_files", ["format"])

    op.create_table(
        "book_authors",
        sa.Column("book_id", sa.Integer, sa.ForeignKey("books.id"), primary_key=True),
        sa.Column("author_id", sa.Integer, sa.ForeignKey("authors.id"), primary_key=True),
    )

    op.create_table(
        "book_tags",
        sa.Column("book_id", sa.Integer, sa.ForeignKey("books.id"), primary_key=True),
        sa.Column("tag_id", sa.Integer, sa.ForeignKey("tags.id"), primary_key=True),
    )

    op.create_table(
        "book_series",
        sa.Column("book_id", sa.Integer, sa.ForeignKey("books.id"), primary_key=True),
        sa.Column("series_id", sa.Integer, sa.ForeignKey("series.id"), primary_key=True),
    )

    op.create_table(
        "shelves",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "shelf_books",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("shelf_id", sa.Integer, sa.ForeignKey("shelves.id"), nullable=False),
        sa.Column("book_id", sa.Integer, sa.ForeignKey("books.id"), nullable=False),
        sa.Column("position", sa.Integer, nullable=False, default=0),
        sa.Column("added_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "devices",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("device_type", sa.String(50), nullable=False),
        sa.Column("device_model", sa.String(255), nullable=True),
        sa.Column("device_id_string", sa.String(255), nullable=True),
        sa.Column("last_synced", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "kobo_sync_tokens",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("device_id", sa.Integer, sa.ForeignKey("devices.id"), nullable=True),
        sa.Column("token", sa.String(64), nullable=False, unique=True),
        sa.Column("is_active", sa.Boolean, nullable=False, default=True),
        sa.Column("books_last_modified", sa.DateTime, nullable=True),
        sa.Column("books_last_created", sa.DateTime, nullable=True),
        sa.Column("reading_state_last_modified", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("last_used", sa.DateTime, nullable=True),
    )
    op.create_index("ix_kobo_sync_tokens_user_id", "kobo_sync_tokens", ["user_id"])
    op.create_index("ix_kobo_sync_tokens_token", "kobo_sync_tokens", ["token"])

    op.create_table(
        "kobo_book_states",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("book_id", sa.Integer, sa.ForeignKey("books.id"), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, default="ReadyToRead"),
        sa.Column("times_started_reading", sa.Integer, nullable=False, default=0),
        sa.Column("total_pages", sa.Integer, nullable=True),
        sa.Column("current_page", sa.Integer, nullable=False, default=0),
        sa.Column("time_spent_reading", sa.Integer, nullable=False, default=0),
        sa.Column("content_source_progress", sa.Float, nullable=False, default=0.0),
        sa.Column("spine_index", sa.Integer, nullable=False, default=0),
        sa.Column("content_id", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_kobo_book_states_user_id", "kobo_book_states", ["user_id"])
    op.create_index("ix_kobo_book_states_book_id", "kobo_book_states", ["book_id"])

    op.create_table(
        "read_progress",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("book_id", sa.Integer, sa.ForeignKey("books.id"), nullable=False),
        sa.Column("device_id", sa.Integer, sa.ForeignKey("devices.id"), nullable=False),
        sa.Column("current_page", sa.Integer, nullable=False, default=0),
        sa.Column("total_pages", sa.Integer, nullable=True),
        sa.Column("percentage", sa.Float, nullable=False, default=0.0),
        sa.Column("status", sa.String(50), nullable=False, default="reading"),
        sa.Column("started_at", sa.DateTime, nullable=True),
        sa.Column("completed_at", sa.DateTime, nullable=True),
        sa.Column("last_opened", sa.DateTime, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "analysis_templates",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("system_prompt", sa.Text, nullable=False),
        sa.Column("user_prompt_template", sa.Text, nullable=False),
        sa.Column("is_default", sa.Boolean, nullable=False, default=False),
        sa.Column("is_builtin", sa.Boolean, nullable=False, default=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_analysis_templates_name", "analysis_templates", ["name"])

    op.create_table(
        "book_analyses",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("book_id", sa.Integer, sa.ForeignKey("books.id"), nullable=False),
        sa.Column("template_id", sa.Integer, sa.ForeignKey("analysis_templates.id"), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("model_used", sa.String(100), nullable=True),
        sa.Column("token_count", sa.Integer, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, default="completed"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_book_analyses_book_id", "book_analyses", ["book_id"])
    op.create_index("ix_book_analyses_status", "book_analyses", ["status"])

    op.create_table(
        "computational_analyses",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("book_id", sa.Integer, sa.ForeignKey("books.id"), nullable=False),
        sa.Column("analysis_type", sa.String(50), nullable=False),
        sa.Column("config_json", sa.Text, nullable=True),
        sa.Column("results_json", sa.Text, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, default="completed"),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_computational_analyses_book_id", "computational_analyses", ["book_id"])
    op.create_index("ix_computational_analyses_analysis_type", "computational_analyses", ["analysis_type"])


def downgrade() -> None:
    op.drop_table("computational_analyses")
    op.drop_table("book_analyses")
    op.drop_table("analysis_templates")
    op.drop_table("read_progress")
    op.drop_table("kobo_book_states")
    op.drop_table("kobo_sync_tokens")
    op.drop_table("devices")
    op.drop_table("shelf_books")
    op.drop_table("shelves")
    op.drop_table("book_series")
    op.drop_table("book_tags")
    op.drop_table("book_authors")
    op.drop_table("book_files")
    op.drop_table("books")
    op.drop_table("series")
    op.drop_table("tags")
    op.drop_table("authors")
    op.drop_table("libraries")
    op.drop_table("users")
