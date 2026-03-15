"""Drop legacy book_id/book columns from all tables after full Works/Editions migration.

THIS IS IRREVERSIBLE. Run only after all application code has been updated
to use the Works/Editions tables and the transition period is complete.

Drops:
  - books.work_id (bridge column — no longer needed)
  - All old book_id FK columns from related tables
  - book_authors, book_tags, book_series junction tables
  - book_contributors table
  - book_files table (data now in edition_files)
  - books table (data now in works + editions)

Revision ID: 0034
Revises: 0033
Create Date: 2026-03-15
"""

import sqlalchemy as sa
from alembic import op

revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop old FK columns from related tables.
    # SQLite batch_alter_table reflects existing indexes and tries to recreate them,
    # so we must explicitly drop any index that references a column being dropped.

    with op.batch_alter_table("kobo_book_states") as batch_op:
        batch_op.drop_index("ix_kobo_book_states_book_id")
        batch_op.drop_column("book_id")

    with op.batch_alter_table("annotations") as batch_op:
        batch_op.drop_index("ix_annotations_book_id")
        batch_op.drop_column("book_id")
        batch_op.drop_column("file_id")  # was FK to book_files

    with op.batch_alter_table("marginalia") as batch_op:
        batch_op.drop_index("ix_marginalia_book_id")
        batch_op.drop_column("book_id")
        batch_op.drop_column("file_id")  # was FK to book_files

    with op.batch_alter_table("shelf_books") as batch_op:
        batch_op.drop_column("book_id")

    with op.batch_alter_table("collection_books") as batch_op:
        batch_op.drop_index("ix_collection_books_book_id")
        batch_op.drop_column("book_id")

    with op.batch_alter_table("collections") as batch_op:
        batch_op.drop_column("cover_book_id")

    with op.batch_alter_table("read_sessions") as batch_op:
        batch_op.drop_index("ix_read_sessions_book_id")
        batch_op.drop_column("book_id")

    with op.batch_alter_table("book_analyses") as batch_op:
        batch_op.drop_index("ix_book_analyses_book_id")
        batch_op.drop_column("book_id")

    with op.batch_alter_table("computational_analyses") as batch_op:
        batch_op.drop_index("ix_computational_analyses_book_id")
        batch_op.drop_column("book_id")

    # book_prompt_configs has a SQLite autoindex on (book_id, template_id) that cannot
    # be dropped by name via batch_alter_table. Use raw SQL to rebuild the table cleanly.
    op.execute("""
        CREATE TABLE book_prompt_configs_new (
            id INTEGER NOT NULL,
            work_id INTEGER,
            template_id INTEGER NOT NULL,
            custom_system_prompt TEXT,
            custom_user_prompt TEXT,
            notes TEXT,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            PRIMARY KEY (id),
            CONSTRAINT uq_work_template_prompt UNIQUE (work_id, template_id)
        )
    """)
    op.execute("""
        INSERT INTO book_prompt_configs_new
            (id, work_id, template_id, custom_system_prompt, custom_user_prompt, notes, created_at, updated_at)
        SELECT id, work_id, template_id, custom_system_prompt, custom_user_prompt, notes, created_at, updated_at
        FROM book_prompt_configs
    """)
    op.drop_table("book_prompt_configs")
    op.rename_table("book_prompt_configs_new", "book_prompt_configs")
    op.create_index("ix_book_prompt_configs_work_id", "book_prompt_configs", ["work_id"])

    with op.batch_alter_table("read_progress") as batch_op:
        batch_op.drop_column("book_id")
        batch_op.drop_column("device_id")  # progress no longer tracked per-device

    # Drop legacy junction and association tables
    op.drop_table("book_series")
    op.drop_table("book_tags")
    op.drop_table("book_authors")

    # Drop book_contributors (split into work_contributors + edition_contributors)
    op.drop_table("book_contributors")

    # Drop book_files (data now in edition_files)
    op.drop_table("book_files")

    # Drop the books table itself — data is now in works + editions
    # (also removes books.work_id bridge)
    op.drop_table("books")


def downgrade() -> None:
    raise NotImplementedError(
        "Migration 0034 is irreversible. Restore from a backup taken before running it."
    )
