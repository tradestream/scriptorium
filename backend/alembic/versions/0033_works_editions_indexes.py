"""Add indexes on new FK columns and rebuild FTS5 search index for works.

Run after migration 0032 (backfill) has been verified.

Revision ID: 0033
Revises: 0032
Create Date: 2026-03-15
"""

import sqlalchemy as sa
from alembic import op

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # Add indexes on backfilled FK columns (SQLite doesn't auto-index FKs)
    op.create_index("ix_books_work_id", "books", ["work_id"])
    op.create_index("ix_kobo_book_states_edition_id", "kobo_book_states", ["edition_id"])
    op.create_index("ix_annotations_edition_id", "annotations", ["edition_id"])
    op.create_index("ix_marginalia_edition_id", "marginalia", ["edition_id"])
    op.create_index("ix_shelf_books_work_id", "shelf_books", ["work_id"])
    op.create_index("ix_collection_books_work_id", "collection_books", ["work_id"])
    op.create_index("ix_read_sessions_work_id", "read_sessions", ["work_id"])
    op.create_index("ix_book_analyses_work_id", "book_analyses", ["work_id"])
    op.create_index("ix_computational_analyses_work_id", "computational_analyses", ["work_id"])
    op.create_index("ix_book_prompt_configs_work_id", "book_prompt_configs", ["work_id"])
    op.create_index("ix_read_progress_edition_id", "read_progress", ["edition_id"])

    # Rebuild FTS5 full-text search index keyed on works.id instead of books.id.
    # Drop the old table (if it exists) and recreate it for works.
    conn.execute(sa.text("DROP TABLE IF EXISTS books_fts"))
    conn.execute(sa.text("""
        CREATE VIRTUAL TABLE IF NOT EXISTS books_fts USING fts5(
            title,
            description,
            authors,
            isbn,
            content='',
            tokenize='unicode61'
        )
    """))

    # Populate FTS from works
    conn.execute(sa.text("""
        INSERT INTO books_fts(rowid, title, description, authors, isbn)
        SELECT
            w.id,
            w.title,
            COALESCE(w.description, ''),
            COALESCE(
                (SELECT GROUP_CONCAT(a.name, ' ')
                 FROM work_authors wa JOIN authors a ON a.id = wa.author_id
                 WHERE wa.work_id = w.id),
                ''
            ),
            COALESCE(
                (SELECT GROUP_CONCAT(e.isbn, ' ')
                 FROM editions e
                 WHERE e.work_id = w.id AND e.isbn IS NOT NULL),
                ''
            )
        FROM works w
    """))


def downgrade() -> None:
    op.drop_index("ix_read_progress_edition_id", "read_progress")
    op.drop_index("ix_book_prompt_configs_work_id", "book_prompt_configs")
    op.drop_index("ix_computational_analyses_work_id", "computational_analyses")
    op.drop_index("ix_book_analyses_work_id", "book_analyses")
    op.drop_index("ix_read_sessions_work_id", "read_sessions")
    op.drop_index("ix_collection_books_work_id", "collection_books")
    op.drop_index("ix_shelf_books_work_id", "shelf_books")
    op.drop_index("ix_marginalia_edition_id", "marginalia")
    op.drop_index("ix_annotations_edition_id", "annotations")
    op.drop_index("ix_kobo_book_states_edition_id", "kobo_book_states")
    op.drop_index("ix_books_work_id", "books")

    # Restore FTS keyed on books
    conn = op.get_bind()
    conn.execute(sa.text("DROP TABLE IF EXISTS books_fts"))
    conn.execute(sa.text("""
        CREATE VIRTUAL TABLE IF NOT EXISTS books_fts USING fts5(
            title,
            description,
            authors,
            isbn,
            content='',
            tokenize='unicode61'
        )
    """))
    conn.execute(sa.text("""
        INSERT INTO books_fts(rowid, title, description, authors, isbn)
        SELECT b.id, b.title, COALESCE(b.description, ''),
               COALESCE((SELECT GROUP_CONCAT(a.name, ' ') FROM book_authors ba
                         JOIN authors a ON a.id = ba.author_id WHERE ba.book_id = b.id), ''),
               COALESCE(b.isbn, '')
        FROM books b
    """))
