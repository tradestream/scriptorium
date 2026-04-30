"""Page-level hash duplicate detection for CBZ comic files.

Hashes individual pages in comic archives to detect:
- Duplicate pages within a single CBZ
- Identical pages across different CBZ files (common with re-scans)

Uses MD5 for speed (not security — just dedup).
"""

import hashlib
import logging
import zipfile
from pathlib import Path

from app.config import resolve_path

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}


def hash_pages(file_path: str) -> list[dict]:
    """Hash all image pages in a CBZ file.

    Returns list of {"page": int, "name": str, "hash": str, "size": int}
    """
    resolved = resolve_path(file_path)
    path = Path(resolved)
    if not path.exists():
        return []

    results = []
    try:
        with zipfile.ZipFile(str(path), "r") as zf:
            images = sorted([
                name for name in zf.namelist()
                if Path(name).suffix.lower() in IMAGE_EXTENSIONS
                and not name.startswith("__MACOSX")
                and not Path(name).name.startswith(".")
            ])
            for i, name in enumerate(images):
                try:
                    data = zf.read(name)
                    h = hashlib.md5(data).hexdigest()
                    results.append({
                        "page": i,
                        "name": name,
                        "hash": h,
                        "size": len(data),
                    })
                except Exception:
                    pass
    except Exception as exc:
        logger.debug("Failed to hash pages in %s: %s", file_path, exc)

    return results


def find_duplicate_pages(file_path: str) -> list[dict]:
    """Find duplicate pages within a single CBZ file.

    Returns list of {"hash": str, "pages": [int, int, ...]}
    """
    pages = hash_pages(file_path)
    hash_map: dict[str, list[int]] = {}
    for p in pages:
        hash_map.setdefault(p["hash"], []).append(p["page"])

    return [
        {"hash": h, "pages": indices}
        for h, indices in hash_map.items()
        if len(indices) > 1
    ]


async def find_cross_file_duplicates(
    edition_ids: list[int],
    db,
) -> list[dict]:
    """Find pages that appear in multiple CBZ files.

    Returns list of {"hash": str, "occurrences": [{"edition_id": int, "page": int, "file": str}]}
    """
    from sqlalchemy import select

    from app.models.edition import EditionFile

    global_hashes: dict[str, list[dict]] = {}

    for eid in edition_ids:
        result = await db.execute(
            select(EditionFile).where(
                EditionFile.edition_id == eid,
                EditionFile.format.in_(["cbz"]),
            )
        )
        for ef in result.scalars().all():
            pages = hash_pages(ef.file_path)
            for p in pages:
                entry = {"edition_id": eid, "page": p["page"], "file": ef.filename}
                global_hashes.setdefault(p["hash"], []).append(entry)

    return [
        {"hash": h, "occurrences": occs}
        for h, occs in global_hashes.items()
        if len(occs) > 1 and len(set(o["edition_id"] for o in occs)) > 1
    ]
