"""Build the page inventory for an EditionFile.

Called from the ingest pipeline for every CBZ / CBR file we import, so
the comic-reader endpoints can serve page count + page extraction with
a single indexed SELECT instead of cracking the archive on every
request.

Public surface:

  * ``populate_pages(file_path, edition_file_id, db)`` — write rows for
    every image entry in the archive. Idempotent: if rows already exist
    for the given ``edition_file_id``, returns without re-scanning.

  * ``ensure_pages(file_path, edition_file_id, db)`` — same as above
    but always returns the count, falling back to a fresh archive walk
    if the cache is empty. Used by the read endpoints during the
    transition while older books are still un-cached.
"""
from __future__ import annotations

import logging
import zipfile
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.page_inventory import EditionFilePage

logger = logging.getLogger(__name__)


# Image extensions we treat as comic pages, mirroring the existing
# read-endpoint set so the inventory matches what users actually see.
_IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".gif")

_MEDIA_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


def _media_type(filename: str) -> str:
    lower = filename.lower()
    for ext, mt in _MEDIA_TYPES.items():
        if lower.endswith(ext):
            return mt
    return "application/octet-stream"


async def populate_pages(
    file_path: Path,
    edition_file_id: int,
    db: AsyncSession,
    *,
    fmt: str = "cbz",
) -> int:
    """Write inventory rows for every image page in the archive.

    Returns the number of rows written. If rows already exist for this
    ``edition_file_id`` we leave them alone and return ``0``: re-scan
    paths should ``DELETE`` first if they want a clean rebuild.
    """
    existing = await db.scalar(
        select(EditionFilePage.id)
        .where(EditionFilePage.edition_file_id == edition_file_id)
        .limit(1)
    )
    if existing is not None:
        return 0

    fmt = fmt.lower()
    if fmt != "cbz":
        # CBR (RAR) handling is future work; rarfile dependency is
        # optional. Skip silently — read endpoints fall through to
        # archive walks.
        return 0

    rows: list[EditionFilePage] = []
    try:
        with zipfile.ZipFile(file_path) as z:
            entries = sorted(
                (info for info in z.infolist() if not info.is_dir()),
                key=lambda i: i.filename,
            )
            page_no = 0
            for info in entries:
                name = info.filename
                lower = name.lower()
                if not lower.endswith(_IMAGE_EXTS):
                    continue
                if lower.startswith("__macosx"):
                    continue
                page_no += 1
                rows.append(
                    EditionFilePage(
                        edition_file_id=edition_file_id,
                        page_number=page_no,
                        filename=name,
                        media_type=_media_type(name),
                        size_bytes=info.file_size if info.file_size else None,
                    )
                )
    except (zipfile.BadZipFile, OSError) as exc:
        logger.warning(
            "page_inventory: failed to read %s for ef=%s: %s",
            file_path,
            edition_file_id,
            exc,
        )
        return 0

    if rows:
        db.add_all(rows)
        await db.flush()
    return len(rows)


async def ensure_pages_count(
    file_path: Path,
    edition_file_id: int,
    db: AsyncSession,
    *,
    fmt: str = "cbz",
) -> Optional[int]:
    """Return the page count using cached inventory when present.

    Falls back to a one-off archive walk (without writing rows) for
    CBZ files that haven't been inventoried yet. Returns ``None`` if
    the format isn't supported or the archive can't be read.
    """
    cached = await db.scalar(
        select(__import__("sqlalchemy").func.count(EditionFilePage.id)).where(
            EditionFilePage.edition_file_id == edition_file_id
        )
    )
    if cached and cached > 0:
        return int(cached)

    if fmt.lower() != "cbz":
        return None
    try:
        with zipfile.ZipFile(file_path) as z:
            return sum(
                1
                for n in z.namelist()
                if n.lower().endswith(_IMAGE_EXTS) and not n.startswith("__MACOSX")
            )
    except (zipfile.BadZipFile, OSError):
        return None
