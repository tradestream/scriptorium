"""
Repair cover_hash / cover_format for books whose cover file exists on disk
but whose DB row has no cover_hash set.

Usage (from within the container):
  PYTHONPATH=/app python3 /app/scripts/repair_cover_hashes.py
"""

import asyncio
import hashlib
from pathlib import Path

from sqlalchemy import select, update

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models.book import Book

settings = get_settings()
COVERS_PATH = Path(settings.COVERS_PATH)
SUPPORTED_EXTS = {"jpg", "jpeg", "png", "webp", "gif"}


async def main() -> None:
    # Build a lookup: uuid -> (hash, format) from the covers directory
    print(f"Scanning {COVERS_PATH} …")
    cover_map: dict[str, tuple[str, str]] = {}
    for f in COVERS_PATH.iterdir():
        # Skip thumbnails
        if "_thumb" in f.stem:
            continue
        ext = f.suffix.lstrip(".").lower()
        if ext not in SUPPORTED_EXTS:
            continue
        uuid = f.stem  # filename without extension
        try:
            data = f.read_bytes()
            h = hashlib.sha256(data).hexdigest()
            cover_map[uuid] = (h, ext)
        except OSError:
            pass
    print(f"  Found {len(cover_map)} cover files")

    async with AsyncSessionLocal() as db:
        # Fetch books with no cover_hash but a matching cover file on disk
        result = await db.execute(
            select(Book.id, Book.uuid, Book.cover_hash).where(Book.cover_hash.is_(None))
        )
        rows = result.all()
        print(f"  {len(rows)} books in DB have no cover_hash")

        updated = 0
        for book_id, uuid, _ in rows:
            if uuid in cover_map:
                h, fmt = cover_map[uuid]
                # Normalise jpg/jpeg
                stored_fmt = "jpg" if fmt == "jpeg" else fmt
                await db.execute(
                    update(Book)
                    .where(Book.id == book_id)
                    .values(cover_hash=h, cover_format=stored_fmt)
                )
                updated += 1

        await db.commit()
        print(f"  Updated {updated} books with cover_hash from disk")


if __name__ == "__main__":
    asyncio.run(main())
