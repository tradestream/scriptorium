"""Loose Leaves — staged review queue for dropped book files.

Unlike the auto-ingest path (INGEST_PATH), files placed in LOOSE_LEAVES_PATH are
*not* automatically imported. They sit in a review queue where admins can:
  - Preview enriched metadata fetched from external providers
  - Import to any library (with optional metadata preview applied)
  - Reject (delete the file from the drop folder)
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models import Library, User
from app.services.scanner import BOOK_EXTENSIONS, _hash_file, _import_book

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/loose-leaves", tags=["loose-leaves"])


def _require_admin(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return current_user


def _loose_leaves_path() -> Path:
    p = Path(settings.LOOSE_LEAVES_PATH)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _guess_title(filename: str) -> str:
    """Derive a probable title from a filename (strips extension and common junk)."""
    stem = Path(filename).stem
    # Replace underscores/dots/dashes with spaces
    stem = re.sub(r"[_.\-]+", " ", stem)
    # Remove common noise patterns like " (Z-Library)", " [epub]", year patterns
    stem = re.sub(r"\s*[\(\[].*?[\)\]]", "", stem)
    stem = re.sub(r"\s*\d{4}\s*$", "", stem)
    return stem.strip()


# ── Schemas ───────────────────────────────────────────────────────────────────

class DropItem(BaseModel):
    filename: str
    size_bytes: int
    format: str
    guessed_title: str


class DropPreview(BaseModel):
    filename: str
    title: Optional[str] = None
    authors: list[str] = []
    description: Optional[str] = None
    tags: list[str] = []
    published_date: Optional[str] = None
    language: Optional[str] = None
    isbn: Optional[str] = None
    cover_url: Optional[str] = None


class ImportRequest(BaseModel):
    filename: str
    library_id: int


class BulkImportRequest(BaseModel):
    """Import multiple files at once, with per-file or default library."""
    files: list[dict]  # [{"filename": str, "library_id": int | null}]
    default_library_id: int


class RejectRequest(BaseModel):
    filename: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/pending", response_model=list[DropItem])
async def list_pending(_admin: User = Depends(_require_admin)):
    """List files currently in the Loose Leaves folder awaiting review."""
    drop_path = _loose_leaves_path()
    items = []
    for f in sorted(drop_path.iterdir()):
        if f.is_file() and f.suffix.lower() in BOOK_EXTENSIONS:
            items.append(
                DropItem(
                    filename=f.name,
                    size_bytes=f.stat().st_size,
                    format=f.suffix.lower().lstrip("."),
                    guessed_title=_guess_title(f.name),
                )
            )
    return items


@router.get("/preview", response_model=DropPreview)
async def preview_metadata(
    filename: str,
    _admin: User = Depends(_require_admin),
):
    """Fetch enriched metadata for a file by querying external providers.

    Uses the guessed title (derived from the filename) and tries all
    configured enrichment providers in priority order.
    """
    drop_path = _loose_leaves_path()
    file_path = drop_path / filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found in Loose Leaves")

    guessed = _guess_title(filename)

    try:
        from app.services.metadata_enrichment import enrichment_service
        result = await enrichment_service.enrich(
            title=guessed,
            authors=[],
            isbn=None,
            file_extension=file_path.suffix.lower(),
        )
    except Exception as exc:
        logger.warning("Loose Leaves preview enrichment failed for %s: %s", filename, exc)
        result = None

    if not result:
        return DropPreview(filename=filename, title=guessed)

    return DropPreview(
        filename=filename,
        title=result.get("title", guessed),
        authors=result.get("authors", []),
        description=result.get("description"),
        tags=result.get("tags", []),
        published_date=result.get("published_date"),
        language=result.get("language"),
        isbn=result.get("isbn"),
        cover_url=result.get("cover_url"),
    )


@router.post("/import", status_code=status.HTTP_200_OK)
async def import_book(
    data: ImportRequest,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(_require_admin),
):
    """Import a file from the Loose Leaves folder into a library."""
    drop_path = _loose_leaves_path()
    file_path = drop_path / data.filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found in Loose Leaves")

    # Verify target library exists
    lib_result = await db.execute(select(Library).where(Library.id == data.library_id))
    library = lib_result.scalar_one_or_none()
    if not library:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Library not found")

    # Check for duplicate by hash
    from app.models import BookFile
    file_hash = _hash_file(file_path)
    existing = await db.scalar(
        select(BookFile.id).where(BookFile.file_hash == file_hash).limit(1)
    )
    if existing:
        # Still remove from drop folder
        file_path.unlink(missing_ok=True)
        return {"status": "duplicate", "message": "Book already exists in library"}

    try:
        book = await _import_book(file_path, file_hash, library, db)
        await db.commit()

        # Move file to library directory
        dest = Path(library.path) / file_path.name
        if not dest.exists():
            file_path.rename(dest)
        else:
            file_path.unlink(missing_ok=True)

        return {
            "status": "imported",
            "book_id": book.id if book else None,
            "message": f"Imported into library '{library.name}'",
        }
    except Exception as exc:
        logger.error("Loose Leaves import failed for %s: %s", data.filename, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.post("/bulk-import")
async def bulk_import_books(
    data: BulkImportRequest,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(_require_admin),
):
    """Import multiple files from Loose Leaves, each with its own library target.

    BookLore-style finalization: per-file library_id with a default fallback.
    """
    drop_path = _loose_leaves_path()
    results = []

    for entry in data.files:
        filename = entry.get("filename", "")
        lib_id = entry.get("library_id") or data.default_library_id
        file_path = drop_path / filename

        if not file_path.exists() or not file_path.is_file():
            results.append({"filename": filename, "status": "not_found"})
            continue

        lib_result = await db.execute(select(Library).where(Library.id == lib_id))
        library = lib_result.scalar_one_or_none()
        if not library:
            results.append({"filename": filename, "status": "invalid_library"})
            continue

        from app.models.edition import EditionFile
        file_hash = _hash_file(file_path)
        existing = await db.scalar(
            select(EditionFile.id).where(EditionFile.file_hash == file_hash).limit(1)
        )
        if existing:
            file_path.unlink(missing_ok=True)
            results.append({"filename": filename, "status": "duplicate"})
            continue

        try:
            result = await _import_book(file_path, file_hash, library, db)
            if result:
                work, edition = result
                await db.commit()
                # Move file
                dest = Path(library.path) / file_path.name
                if file_path.exists():
                    if dest.exists():
                        file_path.unlink(missing_ok=True)
                    else:
                        file_path.rename(dest)
                results.append({"filename": filename, "status": "imported", "book_id": edition.id, "library": library.name})
            else:
                results.append({"filename": filename, "status": "unsupported_format"})
        except Exception as exc:
            logger.error("Bulk import failed for %s: %s", filename, exc)
            results.append({"filename": filename, "status": "error", "message": str(exc)})

    imported = sum(1 for r in results if r["status"] == "imported")
    return {"total": len(data.files), "imported": imported, "results": results}


@router.post("/upload", response_model=list[DropItem])
async def upload_books(
    files: list[UploadFile] = File(...),
    _admin: User = Depends(_require_admin),
):
    """Upload one or more book files directly into the Loose Leaves review queue."""
    drop_path = _loose_leaves_path()
    saved: list[DropItem] = []
    for upload in files:
        if not upload.filename:
            continue
        suffix = Path(upload.filename).suffix.lower()
        if suffix not in BOOK_EXTENSIONS:
            continue
        dest = drop_path / upload.filename
        # Avoid overwriting existing files
        if dest.exists():
            stem = dest.stem
            ext = dest.suffix
            i = 1
            while dest.exists():
                dest = drop_path / f"{stem}_{i}{ext}"
                i += 1
        content = await upload.read()
        dest.write_bytes(content)
        saved.append(
            DropItem(
                filename=dest.name,
                size_bytes=dest.stat().st_size,
                format=suffix.lstrip("."),
                guessed_title=_guess_title(dest.name),
            )
        )
    return saved


@router.delete("/reject", status_code=status.HTTP_204_NO_CONTENT)
async def reject_book(
    data: RejectRequest,
    _admin: User = Depends(_require_admin),
):
    """Reject and delete a file from the Loose Leaves folder."""
    drop_path = _loose_leaves_path()
    file_path = drop_path / data.filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found in Loose Leaves")
    file_path.unlink()
