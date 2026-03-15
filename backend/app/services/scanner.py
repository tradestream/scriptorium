"""Library filesystem scanner — walks a library path and imports new books."""

import hashlib
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Author, Book, BookFile, Edition, EditionFile, Library, Series, Tag, Work
from app.services.covers import cover_service
from app.services.metadata import metadata_service
from app.services.search import search_service

# File extensions considered "books"
BOOK_EXTENSIONS = {".epub", ".pdf", ".cbz", ".cbr", ".mobi", ".azw", ".azw3", ".fb2", ".djvu"}


class ScanResult:
    def __init__(self):
        self.added = 0
        self.skipped = 0
        self.errors: list[str] = []


async def scan_library(library: Library, db: AsyncSession) -> ScanResult:
    """Walk a library's directory and import any books not yet in the database."""
    result = ScanResult()
    library_path = Path(library.path)

    if not library_path.exists():
        result.errors.append(f"Library path does not exist: {library.path}")
        return result

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
            file_hash = _hash_file(file_path)
            file_str = str(file_path)

            if file_hash in existing_hashes or file_str in existing_paths:
                result.skipped += 1
                continue

            await _import_book(file_path, file_hash, library, db)
            existing_hashes.add(file_hash)
            existing_paths.add(file_str)
            result.added += 1
        except Exception as exc:
            result.errors.append(f"{file_path.name}: {exc}")

    # Update last_scanned timestamp
    library.last_scanned = datetime.utcnow()
    await db.commit()
    return result


async def _import_book(
    file_path: Path, file_hash: str, library: Library, db: AsyncSession
) -> "tuple[Work, Edition] | None":
    """Create Work + Edition + EditionFile records for a single file.

    Also creates the legacy Book + BookFile rows for backward compatibility
    during the transition period (until migration 0034 is run).

    Returns (work, edition) on success, None if the file format is unrecognised.
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
    if meta.get("cover_image"):
        cover_hash, cover_format = await cover_service.save_cover(meta["cover_image"], entity_uuid)

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
        published_date=meta.get("published_date"),
        language=meta.get("language"),
        format=fmt,
        cover_hash=cover_hash,
        cover_format=cover_format,
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

    # ── Legacy Book + BookFile (compatibility shim until migration 0034) ───────
    book = Book(
        uuid=entity_uuid,
        title=meta["title"],
        description=meta.get("description"),
        isbn=meta.get("isbn"),
        language=meta.get("language"),
        published_date=meta.get("published_date"),
        cover_hash=cover_hash,
        cover_format=cover_format,
        library_id=library.id,
        work_id=work.id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        authors=authors,
    )
    db.add(book)
    await db.flush()

    book_file = BookFile(
        book_id=book.id,
        filename=file_path.name,
        format=fmt,
        file_path=str(file_path),
        file_hash=file_hash + "_legacy",  # avoid unique constraint clash with edition_files
        file_size=file_path.stat().st_size,
        created_at=datetime.utcnow(),
    )
    db.add(book_file)

    await db.commit()

    # ── Index in FTS5 ─────────────────────────────────────────────────────────
    author_names = [a.name for a in authors]
    await search_service.index_work(db, work, author_names)

    return work, edition


async def _get_or_create_entities(
    db: AsyncSession, model, field: str, names: list[str]
) -> list:
    """Return model instances for each name, creating missing ones."""
    entities = []
    for name in names:
        name = name.strip()
        if not name:
            continue
        result = await db.execute(select(model).where(getattr(model, field) == name))
        entity = result.scalar_one_or_none()
        if entity is None:
            entity = model(**{field: name})
            db.add(entity)
            await db.flush()
        entities.append(entity)
    return entities


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
