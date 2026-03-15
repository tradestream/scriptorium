"""Backfill works and editions from existing books.

For every existing Book row:
  - Creates one Work row (work-level fields)
  - Creates one Edition row (edition-level fields, same uuid as book)
  - Creates one EditionFile row per BookFile
  - Mirrors all association table rows (authors, tags, series)
  - Splits BookContributors: translators → edition_contributors,
    editors/illustrators/colorists → work_contributors
  - Backfills all new FK columns in related tables
  - Migrates read_progress → user_editions (one row per user+edition,
    highest-percentage progress wins)

Revision ID: 0032
Revises: 0031
Create Date: 2026-03-15
"""

from alembic import op
import sqlalchemy as sa

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # ── Step 1: Create one Work per Book ──────────────────────────────────────
    conn.execute(sa.text("""
        INSERT INTO works (uuid, title, subtitle, description, language,
                           locked_fields, esoteric_enabled, created_at, updated_at)
        SELECT uuid, title, subtitle, description, language,
               locked_fields, esoteric_enabled, created_at, updated_at
        FROM books
    """))

    # Step 1b: Update books.work_id bridge
    conn.execute(sa.text("""
        UPDATE books
        SET work_id = (SELECT id FROM works WHERE works.uuid = books.uuid)
    """))

    # ── Step 2: Create one Edition per Book ───────────────────────────────────
    # Derive format from the first BookFile for that book (most common format)
    conn.execute(sa.text("""
        INSERT INTO editions (uuid, work_id, library_id, isbn, publisher,
                              published_date, language, format, cover_hash,
                              cover_format, locked_fields, abs_item_id,
                              physical_copy, created_at, updated_at)
        SELECT b.uuid,
               w.id,
               b.library_id,
               b.isbn,
               b.publisher,
               b.published_date,
               b.language,
               (SELECT bf.format FROM book_files bf WHERE bf.book_id = b.id
                ORDER BY bf.id LIMIT 1),
               b.cover_hash,
               b.cover_format,
               b.locked_fields,
               b.abs_item_id,
               b.physical_copy,
               b.created_at,
               b.updated_at
        FROM books b
        JOIN works w ON w.uuid = b.uuid
    """))

    # ── Step 3: Create EditionFiles from BookFiles ────────────────────────────
    conn.execute(sa.text("""
        INSERT INTO edition_files (edition_id, filename, format, file_path,
                                   file_hash, file_size, created_at)
        SELECT e.id, bf.filename, bf.format, bf.file_path,
               bf.file_hash, bf.file_size, bf.created_at
        FROM book_files bf
        JOIN books b ON b.id = bf.book_id
        JOIN editions e ON e.uuid = b.uuid
    """))

    # ── Step 4: Mirror association tables ─────────────────────────────────────
    conn.execute(sa.text("""
        INSERT INTO work_authors (work_id, author_id)
        SELECT w.id, ba.author_id
        FROM book_authors ba
        JOIN books b ON b.id = ba.book_id
        JOIN works w ON w.uuid = b.uuid
    """))

    conn.execute(sa.text("""
        INSERT INTO work_tags (work_id, tag_id)
        SELECT w.id, bt.tag_id
        FROM book_tags bt
        JOIN books b ON b.id = bt.book_id
        JOIN works w ON w.uuid = b.uuid
    """))

    conn.execute(sa.text("""
        INSERT INTO work_series (work_id, series_id, position, volume, arc)
        SELECT w.id, bs.series_id, bs.position, bs.volume, bs.arc
        FROM book_series bs
        JOIN books b ON b.id = bs.book_id
        JOIN works w ON w.uuid = b.uuid
    """))

    # ── Step 5: Split BookContributors ────────────────────────────────────────
    # Translators → edition_contributors
    conn.execute(sa.text("""
        INSERT INTO edition_contributors (edition_id, name, role)
        SELECT e.id, bc.name, bc.role
        FROM book_contributors bc
        JOIN books b ON b.id = bc.book_id
        JOIN editions e ON e.uuid = b.uuid
        WHERE bc.role = 'translator'
    """))

    # Editors / illustrators / colorists → work_contributors
    conn.execute(sa.text("""
        INSERT INTO work_contributors (work_id, name, role)
        SELECT w.id, bc.name, bc.role
        FROM book_contributors bc
        JOIN books b ON b.id = bc.book_id
        JOIN works w ON w.uuid = b.uuid
        WHERE bc.role != 'translator'
    """))

    # ── Step 6: Backfill FK columns in related tables ─────────────────────────

    # kobo_book_states.edition_id
    conn.execute(sa.text("""
        UPDATE kobo_book_states
        SET edition_id = (
            SELECT e.id FROM editions e
            JOIN books b ON b.uuid = e.uuid
            WHERE b.id = kobo_book_states.book_id
        )
    """))

    # annotations.edition_id
    conn.execute(sa.text("""
        UPDATE annotations
        SET edition_id = (
            SELECT e.id FROM editions e
            JOIN books b ON b.uuid = e.uuid
            WHERE b.id = annotations.book_id
        )
    """))

    # marginalia.edition_id
    conn.execute(sa.text("""
        UPDATE marginalia
        SET edition_id = (
            SELECT e.id FROM editions e
            JOIN books b ON b.uuid = e.uuid
            WHERE b.id = marginalia.book_id
        )
    """))

    # shelf_books.work_id
    conn.execute(sa.text("""
        UPDATE shelf_books
        SET work_id = (
            SELECT b.work_id FROM books b WHERE b.id = shelf_books.book_id
        )
    """))

    # collection_books.work_id
    conn.execute(sa.text("""
        UPDATE collection_books
        SET work_id = (
            SELECT b.work_id FROM books b WHERE b.id = collection_books.book_id
        )
    """))

    # collections.cover_work_id
    conn.execute(sa.text("""
        UPDATE collections
        SET cover_work_id = (
            SELECT b.work_id FROM books b WHERE b.id = collections.cover_book_id
        )
        WHERE cover_book_id IS NOT NULL
    """))

    # read_sessions.work_id
    conn.execute(sa.text("""
        UPDATE read_sessions
        SET work_id = (
            SELECT b.work_id FROM books b WHERE b.id = read_sessions.book_id
        )
    """))

    # book_analyses.work_id
    conn.execute(sa.text("""
        UPDATE book_analyses
        SET work_id = (
            SELECT b.work_id FROM books b WHERE b.id = book_analyses.book_id
        )
    """))

    # computational_analyses.work_id
    conn.execute(sa.text("""
        UPDATE computational_analyses
        SET work_id = (
            SELECT b.work_id FROM books b WHERE b.id = computational_analyses.book_id
        )
    """))

    # book_prompt_configs.work_id
    conn.execute(sa.text("""
        UPDATE book_prompt_configs
        SET work_id = (
            SELECT b.work_id FROM books b WHERE b.id = book_prompt_configs.book_id
        )
    """))

    # read_progress.edition_id
    conn.execute(sa.text("""
        UPDATE read_progress
        SET edition_id = (
            SELECT e.id FROM editions e
            JOIN books b ON b.uuid = e.uuid
            WHERE b.id = read_progress.book_id
        )
    """))

    # ── Step 7: Migrate read_progress → user_editions ─────────────────────────
    # One row per (user_id, edition_id) — pick the highest-percentage row when
    # multiple devices have different progress for the same user+book.
    conn.execute(sa.text("""
        INSERT INTO user_editions (
            user_id, edition_id, status, current_page, total_pages,
            percentage, rating, started_at, completed_at, last_opened,
            created_at, updated_at
        )
        SELECT
            rp.user_id,
            rp.edition_id,
            rp.status,
            rp.current_page,
            rp.total_pages,
            rp.percentage,
            rp.rating,
            rp.started_at,
            rp.completed_at,
            MAX(rp.last_opened),
            MIN(rp.created_at),
            MAX(rp.updated_at)
        FROM read_progress rp
        WHERE rp.edition_id IS NOT NULL
        GROUP BY rp.user_id, rp.edition_id
        HAVING rp.percentage = MAX(rp.percentage)
    """))


def downgrade() -> None:
    # Remove backfilled user_editions rows (those that came from read_progress)
    # We can't precisely identify them after the fact, so we clear the whole table.
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM user_editions"))
    conn.execute(sa.text("DELETE FROM edition_contributors"))
    conn.execute(sa.text("DELETE FROM work_contributors"))
    conn.execute(sa.text("DELETE FROM work_series"))
    conn.execute(sa.text("DELETE FROM work_tags"))
    conn.execute(sa.text("DELETE FROM work_authors"))
    conn.execute(sa.text("DELETE FROM edition_files"))
    conn.execute(sa.text("DELETE FROM editions"))
    conn.execute(sa.text("UPDATE books SET work_id = NULL"))
    conn.execute(sa.text("DELETE FROM works"))
    # Clear backfilled FK columns
    conn.execute(sa.text("UPDATE kobo_book_states SET edition_id = NULL"))
    conn.execute(sa.text("UPDATE annotations SET edition_id = NULL"))
    conn.execute(sa.text("UPDATE marginalia SET edition_id = NULL"))
    conn.execute(sa.text("UPDATE shelf_books SET work_id = NULL"))
    conn.execute(sa.text("UPDATE collection_books SET work_id = NULL"))
    conn.execute(sa.text("UPDATE collections SET cover_work_id = NULL"))
    conn.execute(sa.text("UPDATE read_sessions SET work_id = NULL"))
    conn.execute(sa.text("UPDATE book_analyses SET work_id = NULL"))
    conn.execute(sa.text("UPDATE computational_analyses SET work_id = NULL"))
    conn.execute(sa.text("UPDATE book_prompt_configs SET work_id = NULL"))
    conn.execute(sa.text("UPDATE read_progress SET edition_id = NULL"))
