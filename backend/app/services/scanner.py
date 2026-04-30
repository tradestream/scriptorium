"""Library filesystem scanner — walks a library path and imports new books."""

import hashlib
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Author, BookFile, Edition, EditionFile, Library, Work
from app.services.covers import cover_service
from app.services.metadata import metadata_service
from app.services.search import search_service

# File extensions considered "books"
BOOK_EXTENSIONS = {".epub", ".pdf", ".cbz", ".cbr", ".mobi", ".azw", ".azw3", ".fb2", ".djvu"}


class ScanResult:
    def __init__(self):
        self.added = 0
        self.skipped = 0
        self.excluded = 0  # files filtered by exclude_patterns
        self.errors: list[str] = []


async def scan_library(library: Library, db: AsyncSession) -> ScanResult:
    """Walk a library's directory and import any books not yet in the database."""
    from app.config import resolve_path as _rp
    from app.services.exclude_patterns import build_matcher, is_excluded

    result = ScanResult()
    # The library's stored ``path`` is the container shape (e.g.
    # ``/data/library/...``); ``resolve_path`` translates to a host
    # path when running outside Docker. Both the walk root and the
    # ``.scriptoriumignore`` lookup use the host form.
    library_path = Path(_rp(library.path))

    if not library_path.exists():
        result.errors.append(f"Library path does not exist: {library.path}")
        return result

    matcher = build_matcher(library_path, library.exclude_patterns)

    # Collect all existing file hashes/paths to skip duplicates quickly.
    # Check both EditionFile (new) and BookFile (legacy) tables.
    existing_hashes: set[str] = set()
    existing_paths: set[str] = set()
    for row in await db.execute(select(EditionFile.file_hash, EditionFile.file_path)):
        existing_hashes.add(row.file_hash)
        existing_paths.add(row.file_path)
    for row in await db.execute(select(BookFile.file_hash, BookFile.file_path)):
        existing_hashes.add(row.file_hash)
        existing_paths.add(row.file_path)

    for file_path in _walk_books(library_path):
        try:
            if is_excluded(file_path, library_path, matcher):
                result.excluded += 1
                continue
            file_hash = _hash_file(file_path)
            file_str = str(file_path)

            if file_hash in existing_hashes or file_str in existing_paths:
                result.skipped += 1
                continue

            imported = await _import_book(file_path, file_hash, library, db)
            existing_hashes.add(file_hash)
            existing_paths.add(file_str)
            result.added += 1
            # Pre-emptive KEPUB conversion (Kobo-first households). The
            # file is already at its final library path here, so the
            # cached kepub_path won't be invalidated by a later move.
            if imported is not None:
                _, edition, edition_file = imported
                _schedule_kepub_for_edition_file(edition, edition_file)
        except Exception as exc:
            result.errors.append(f"{file_path.name}: {exc}")

    # Update last_scanned timestamp
    library.last_scanned = datetime.utcnow()
    await db.commit()
    return result


async def _import_book(
    file_path: Path, file_hash: str, library: Library, db: AsyncSession
) -> "tuple[Work, Edition, EditionFile] | None":
    """Create Work + Edition + EditionFile records for a single file.

    Returns (work, edition, edition_file) on success, None if the file
    format is unrecognised. The EditionFile is returned so callers can
    chain follow-on work (KEPUB conversion, identifier extraction)
    without re-fetching it.
    """
    fmt = metadata_service.detect_format(file_path)
    if fmt is None:
        return None

    # ── Extract metadata ──────────────────────────────────────────────────────
    extractor = {
        "epub": metadata_service.extract_from_epub,
        "pdf": metadata_service.extract_from_pdf,
        "cbz": metadata_service.extract_from_cbz,
        "cbr": metadata_service.extract_from_cbz,
    }.get(fmt)

    meta = await extractor(file_path) if extractor else {
        "title": file_path.stem,
        "authors": [],
        "description": None,
        "isbn": None,
        "language": None,
        "published_date": None,
        "cover_image": None,
    }

    entity_uuid = str(uuid.uuid4())

    # ── Save cover ────────────────────────────────────────────────────────────
    cover_hash: Optional[str] = None
    cover_format: Optional[str] = None
    cover_color: Optional[str] = None
    if meta.get("cover_image"):
        cover_hash, cover_format, cover_color = await cover_service.save_cover(meta["cover_image"], entity_uuid)

    # ── Resolve or create authors ─────────────────────────────────────────────
    authors = await _get_or_create_entities(db, Author, "name", meta.get("authors", []))

    # ── Create Work ───────────────────────────────────────────────────────────
    work = Work(
        uuid=entity_uuid,
        title=meta["title"],
        description=meta.get("description"),
        language=meta.get("language"),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        authors=authors,
    )
    db.add(work)
    await db.flush()  # get work.id

    # ── Create Edition ────────────────────────────────────────────────────────
    edition = Edition(
        uuid=entity_uuid,          # same UUID as the Work — stable for Kobo sync
        work_id=work.id,
        library_id=library.id,
        isbn=meta.get("isbn"),
        isbn_10=meta.get("isbn_10"),
        published_date=meta.get("published_date"),
        language=meta.get("language"),
        format=fmt,
        cover_hash=cover_hash,
        cover_format=cover_format,
        cover_color=cover_color,
        is_fixed_layout=bool(meta.get("is_fixed_layout")),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(edition)
    await db.flush()  # get edition.id

    edition_file = EditionFile(
        edition_id=edition.id,
        filename=file_path.name,
        format=fmt,
        file_path=str(file_path),
        file_hash=file_hash,
        file_size=file_path.stat().st_size,
        created_at=datetime.utcnow(),
    )
    db.add(edition_file)

    # ── ComicInfo.xml extraction for CBZ/CBR ──────────────────────────────────
    if fmt in ("cbz", "cbr"):
        try:
            from app.services.comicinfo import (
                apply_comicinfo,
                parse_comicinfo_from_cbr,
                parse_comicinfo_from_cbz,
            )
            parser = parse_comicinfo_from_cbz if fmt == "cbz" else parse_comicinfo_from_cbr
            comicinfo = parser(str(file_path))
            if comicinfo:
                await apply_comicinfo(work, edition, comicinfo, db)
        except Exception:
            pass  # ComicInfo extraction is non-critical

    # ── Page inventory cache (CBZ) ────────────────────────────────────────────
    # Walk the archive once now so the comic reader serves
    # ``GET /pages`` and ``/pages/{n}`` from an indexed table instead
    # of cracking the ZIP per request.
    if fmt == "cbz":
        try:
            from app.services.page_inventory import populate_pages
            await populate_pages(file_path, edition_file.id, db, fmt=fmt)
        except Exception:
            pass  # inventory is a perf cache; failures fall back to live walk

    await db.commit()

    # ── Index in FTS5 (non-critical) ──────────────────────────────────────────
    try:
        author_names = [a.name for a in authors]
        await search_service.index_work(db, work, author_names)
    except Exception:
        pass  # FTS indexing is non-critical; search will work without it

    return work, edition, edition_file


async def _get_or_create_entities(
    db: AsyncSession, model, field: str, names: list[str]
) -> list:
    """Return model instances for each name, creating missing ones.

    Handles race conditions from concurrent workers by catching
    UNIQUE constraint errors and retrying with a fresh lookup.
    """
    entities = []
    for name in names:
        name = name.strip()
        if not name:
            continue
        result = await db.execute(select(model).where(getattr(model, field) == name))
        entity = result.scalar_one_or_none()
        if entity is None:
            try:
                entity = model(**{field: name})
                db.add(entity)
                await db.flush()
            except Exception:
                # UNIQUE constraint — another worker created it concurrently
                await db.rollback()
                result = await db.execute(select(model).where(getattr(model, field) == name))
                entity = result.scalar_one_or_none()
                if entity is None:
                    continue  # skip if still not found after rollback
        entities.append(entity)
    return entities


def _schedule_kepub_for_edition_file(edition: "Edition", edition_file: "EditionFile") -> None:
    """Schedule post-import KEPUB conversion if enabled and applicable.

    Runs after the row is committed and the file is at its final
    location. No-op for non-EPUB editions, fixed-layout EPUBs, or when
    ``KEPUB_AUTO_CONVERT`` is disabled.
    """
    from app.config import get_settings as _gs
    if not _gs().KEPUB_AUTO_CONVERT:
        return
    if (edition_file.format or "").lower() != "epub":
        return
    if edition.is_fixed_layout:
        return
    from app.services.kepub import schedule_kepub_conversion
    schedule_kepub_conversion(edition_file.id)


def _walk_books(root: Path):
    """Yield all book files under root recursively."""
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in BOOK_EXTENSIONS:
            yield path


def _hash_file(path: Path) -> str:
    """SHA-256 hash of file contents."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
