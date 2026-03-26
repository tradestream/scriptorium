"""Markdown caching service — pre-converts book files to LLM-optimized markdown.

Stores cached markdown at {MARKDOWN_PATH}/{edition_uuid}.md so analyses and
other LLM features can skip the expensive extraction step.

Skips audiobooks (ABS-only, no local files) and comics (image-based).
"""

import logging
from pathlib import Path

from app.config import get_settings

logger = logging.getLogger("scriptorium.markdown")

settings = get_settings()
MARKDOWN_DIR = Path(settings.MARKDOWN_PATH)

# Formats that cannot produce meaningful markdown
_SKIP_FORMATS = {"cbz", "cbr", "cb7", "m4b", "mp3", "m4a", "ogg", "flac"}


def markdown_path_for(edition_uuid: str) -> Path:
    """Return the cache path for an edition's markdown file."""
    return MARKDOWN_DIR / f"{edition_uuid}.md"


def has_cached_markdown(edition_uuid: str) -> bool:
    """Check if cached markdown already exists for an edition."""
    p = markdown_path_for(edition_uuid)
    return p.exists() and p.stat().st_size > 0


async def generate_markdown(edition_id: int) -> str | None:
    """Extract and cache markdown for a single edition.

    Returns the markdown text on success, None if skipped or failed.
    """
    from sqlalchemy import select
    from sqlalchemy.orm import joinedload
    from app.database import get_session_factory
    from app.models.edition import Edition, EditionFile
    from app.models.work import Work
    from app.services.text_extraction import (
        _extract_epub_markdown,
        _extract_pdf_text,
        optimize_for_llm,
    )

    factory = get_session_factory()
    async with factory() as db:
        result = await db.execute(
            select(Edition)
            .where(Edition.id == edition_id)
            .options(
                joinedload(Edition.files),
                joinedload(Edition.work).options(joinedload(Work.authors)),
            )
        )
        edition = result.unique().scalar_one_or_none()
        if not edition:
            return None

        # Already cached?
        if has_cached_markdown(edition.uuid):
            return markdown_path_for(edition.uuid).read_text(encoding="utf-8")

        files = edition.files
        if not files:
            return None

        # Pick best file for text extraction
        format_priority = {"epub": 0, "txt": 1, "pdf": 2, "mobi": 3, "azw": 4, "azw3": 5}
        sorted_files = sorted(files, key=lambda f: format_priority.get(f.format.lower(), 99))
        best_file = sorted_files[0]
        fmt = best_file.format.lower()

        if fmt in _SKIP_FORMATS:
            return None

        file_path = Path(best_file.file_path)
        if not file_path.exists():
            logger.debug("File missing for edition %d: %s", edition_id, file_path)
            return None

        try:
            if fmt == "epub":
                text = await _extract_epub_markdown(file_path)
            elif fmt == "pdf":
                text = await _extract_pdf_text(file_path)
            elif fmt in ("txt", "text"):
                text = file_path.read_text(encoding="utf-8", errors="replace")
            elif fmt in ("mobi", "azw", "azw3"):
                # Try mobi extraction → epub → markdown
                text = await _extract_mobi_via_epub(file_path)
                if not text:
                    return None
            else:
                logger.debug("Unsupported format for markdown: %s", fmt)
                return None

            # Apply LLM optimizations (no truncation — store full text)
            author_name = None
            if edition.work and edition.work.authors:
                author_name = edition.work.authors[0].name
            text = optimize_for_llm(text, title=edition.title, author=author_name)

            # Cache to disk
            MARKDOWN_DIR.mkdir(parents=True, exist_ok=True)
            out_path = markdown_path_for(edition.uuid)
            out_path.write_text(text, encoding="utf-8")
            logger.info("Cached markdown for edition %d (%s)", edition_id, edition.title)
            return text

        except Exception as exc:
            logger.warning("Markdown generation failed for edition %d: %s", edition_id, exc)
            return None


def generate_markdown_sync(edition_id: int) -> str | None:
    """Sync version for background threads. Uses sqlite3 directly."""
    import sqlite3
    from app.services.text_extraction import (
        _extract_epub_markdown_sync,
        _extract_pdf_pdfplumber_sync,
        optimize_for_llm,
    )
    from app.services.background_jobs import _get_sync_db_path

    db_path = _get_sync_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("""
            SELECT e.id, e.uuid, e.title as edition_title,
                   w.title as work_title, w.id as work_id
            FROM editions e
            JOIN works w ON w.id = e.work_id
            WHERE e.id = ?
        """, (edition_id,)).fetchone()
        if not row:
            return None

        title = row["work_title"] or row["edition_title"]
        uuid = row["uuid"]

        if has_cached_markdown(uuid):
            return markdown_path_for(uuid).read_text(encoding="utf-8")

        # Get best file
        files = conn.execute("""
            SELECT file_path, format FROM edition_files
            WHERE edition_id = ? ORDER BY
            CASE format
                WHEN 'epub' THEN 0 WHEN 'txt' THEN 1
                WHEN 'pdf' THEN 2 WHEN 'mobi' THEN 3
                WHEN 'azw3' THEN 4 ELSE 99
            END
        """, (edition_id,)).fetchall()
        if not files:
            return None

        best = files[0]
        fmt = best["format"].lower()
        file_path = Path(best["file_path"])

        if fmt in _SKIP_FORMATS:
            return None
        if not file_path.exists():
            logger.debug("File missing for edition %d: %s", edition_id, file_path)
            return None

        # Get author
        author_row = conn.execute("""
            SELECT a.name FROM authors a
            JOIN work_authors wa ON wa.author_id = a.id
            WHERE wa.work_id = ? LIMIT 1
        """, (row["work_id"],)).fetchone()
        author_name = author_row["name"] if author_row else None

        try:
            if fmt == "epub":
                text = _extract_epub_markdown_sync(file_path)
            elif fmt == "pdf":
                text = _extract_pdf_pdfplumber_sync(file_path)
            elif fmt in ("txt", "text"):
                text = file_path.read_text(encoding="utf-8", errors="replace")
            else:
                return None

            text = optimize_for_llm(text, title=title, author=author_name)

            MARKDOWN_DIR.mkdir(parents=True, exist_ok=True)
            out_path = markdown_path_for(uuid)
            out_path.write_text(text, encoding="utf-8")
            logger.info("Cached markdown for edition %d (%s)", edition_id, title)
            return text

        except Exception as exc:
            logger.warning("Markdown sync failed for edition %d: %s", edition_id, exc)
            return None
    finally:
        conn.close()


async def _extract_mobi_via_epub(path: Path) -> str | None:
    """Extract markdown from MOBI/AZW by converting to EPUB first."""
    try:
        from app.services.conversion import _mobi_to_epub
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        await _mobi_to_epub(path, tmp_path)
        if tmp_path.exists() and tmp_path.stat().st_size > 0:
            from app.services.text_extraction import _extract_epub_markdown
            text = await _extract_epub_markdown(tmp_path)
            tmp_path.unlink(missing_ok=True)
            return text
        return None
    except Exception as exc:
        logger.debug("MOBI→EPUB→markdown failed for %s: %s", path, exc)
        return None
