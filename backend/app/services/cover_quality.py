"""Cover quality analysis and iTunes cover upgrade service.

Analyzes existing covers for resolution/size, searches iTunes for
high-resolution replacements, and upgrades low-quality covers.
"""

import logging
import re
from typing import Optional

import httpx

from app.config import get_settings

logger = logging.getLogger("scriptorium.cover_quality")

settings = get_settings()

# Quality thresholds
MIN_WIDTH = 400
MIN_HEIGHT = 600
MIN_FILE_SIZE = 20_000  # 20 KB

# iTunes API
ITUNES_LOOKUP = "https://itunes.apple.com/lookup"
ITUNES_SEARCH = "https://itunes.apple.com/search"
ITUNES_COUNTRIES = ["us", "gb", "au"]


# ── Cover Quality Analysis ───────────────────────────────────────────────────

def analyze_cover(cover_bytes: bytes) -> dict:
    """Analyze cover image quality.

    Returns dict with width, height, file_size, is_low_quality, reasons.
    """
    try:
        from PIL import Image
        import io

        file_size = len(cover_bytes)
        img = Image.open(io.BytesIO(cover_bytes))
        width, height = img.size

        reasons = []
        if width < MIN_WIDTH:
            reasons.append(f"width={width}<{MIN_WIDTH}")
        if height < MIN_HEIGHT:
            reasons.append(f"height={height}<{MIN_HEIGHT}")
        if file_size < MIN_FILE_SIZE:
            reasons.append(f"size={file_size // 1024}KB<{MIN_FILE_SIZE // 1024}KB")

        return {
            "width": width,
            "height": height,
            "file_size": file_size,
            "is_low_quality": len(reasons) > 0,
            "reasons": reasons,
        }
    except Exception as exc:
        return {"width": 0, "height": 0, "file_size": 0, "is_low_quality": True, "reasons": [str(exc)]}


async def analyze_edition_cover(edition_uuid: str, cover_format: str) -> dict | None:
    """Analyze a stored cover file's quality."""
    from pathlib import Path

    covers_path = Path(settings.COVERS_PATH)
    cover_file = covers_path / f"{edition_uuid}.{cover_format}"
    if not cover_file.exists():
        return None
    return analyze_cover(cover_file.read_bytes())


# ── iTunes Cover Search ──────────────────────────────────────────────────────

def _normalize_title(title: str) -> str:
    """Normalize title for comparison."""
    if not title:
        return ""
    title = re.sub(r'\.(epub|pdf|mobi|azw3?)$', '', title, flags=re.IGNORECASE)
    title = title.lower()
    title = re.sub(r'[^\w\s]', ' ', title)
    return re.sub(r'\s+', ' ', title).strip()


def _titles_match(title1: str, title2: str, threshold: float = 0.5) -> bool:
    """Check if titles are similar enough via word overlap."""
    words1 = set(_normalize_title(title1).split())
    words2 = set(_normalize_title(title2).split())
    if not words1 or not words2:
        return False
    smaller, larger = (words1, words2) if len(words1) <= len(words2) else (words2, words1)
    if smaller.issubset(larger) and len(smaller) >= 2:
        return True
    intersection = len(words1 & words2)
    union = len(words1 | words2)
    return (intersection / union if union else 0) >= threshold


def _highres_url(artwork_url: str, size: str = "1200x1200bb") -> str | None:
    """Convert iTunes thumbnail URL to high-res URL."""
    if not artwork_url:
        return None
    base = artwork_url.rsplit('/', 1)[0] + '/'
    return base + f"{size}.jpg"


async def search_itunes_cover(
    isbn: str | None = None,
    title: str | None = None,
    author: str | None = None,
) -> dict | None:
    """Search iTunes for a high-res book cover.

    Tries ISBN lookup first across multiple countries, then title+author search.
    Verifies title match to avoid wrong covers.

    Returns dict with url, itunes_title, itunes_author, or None.
    """
    async with httpx.AsyncClient(timeout=10) as client:
        # Try ISBN lookup
        if isbn:
            for country in ITUNES_COUNTRIES:
                try:
                    r = await client.get(ITUNES_LOOKUP, params={
                        "isbn": isbn, "entity": "ebook", "country": country, "limit": 1,
                    })
                    if r.status_code == 200:
                        data = r.json()
                        if data.get("resultCount", 0) > 0:
                            result = data["results"][0]
                            itunes_title = result.get("trackName", "")
                            if not title or _titles_match(title, itunes_title):
                                return {
                                    "url": _highres_url(result.get("artworkUrl100")),
                                    "itunes_title": itunes_title,
                                    "itunes_author": result.get("artistName", ""),
                                }
                except Exception:
                    continue

        # Fall back to title+author search
        if title:
            query = f"{title} {author}" if author else title
            for country in ITUNES_COUNTRIES:
                try:
                    r = await client.get(ITUNES_SEARCH, params={
                        "term": query, "entity": "ebook", "country": country, "limit": 5,
                    })
                    if r.status_code == 200:
                        data = r.json()
                        for result in data.get("results", []):
                            itunes_title = result.get("trackName", "")
                            if _titles_match(title, itunes_title):
                                return {
                                    "url": _highres_url(result.get("artworkUrl100")),
                                    "itunes_title": itunes_title,
                                    "itunes_author": result.get("artistName", ""),
                                }
                except Exception:
                    continue

    return None


# ── Bulk Analysis & Upgrade ──────────────────────────────────────────────────

async def find_low_quality_covers(library_id: int | None = None) -> list[dict]:
    """Find editions with low-quality or missing covers.

    Returns list of dicts with edition_id, title, isbn, quality info.
    """
    from sqlalchemy import select
    from sqlalchemy.orm import joinedload
    from app.database import get_session_factory
    from app.models.edition import Edition
    from app.models.work import Work
    from pathlib import Path

    factory = get_session_factory()
    covers_path = Path(settings.COVERS_PATH)
    results = []

    async with factory() as db:
        stmt = (
            select(Edition)
            .join(Edition.work)
            .options(joinedload(Edition.work).options(joinedload(Work.authors)))
            .where(Edition.cover_hash.isnot(None))
        )
        if library_id:
            stmt = stmt.where(Edition.library_id == library_id)

        editions = (await db.execute(stmt)).unique().scalars().all()

        for ed in editions:
            if not ed.cover_format:
                continue
            cover_file = covers_path / f"{ed.uuid}.{ed.cover_format}"
            if not cover_file.exists():
                continue

            quality = analyze_cover(cover_file.read_bytes())
            if quality["is_low_quality"]:
                results.append({
                    "edition_id": ed.id,
                    "title": ed.title,
                    "isbn": ed.isbn,
                    "authors": [a.name for a in (ed.work.authors if ed.work else [])],
                    "width": quality["width"],
                    "height": quality["height"],
                    "file_size": quality["file_size"],
                    "reasons": quality["reasons"],
                })

    return results


async def upgrade_cover(edition_id: int) -> dict:
    """Try to upgrade a single edition's cover via iTunes.

    Returns dict with status, itunes_title, etc.
    """
    import asyncio
    from sqlalchemy import select
    from sqlalchemy.orm import joinedload
    from app.database import get_session_factory
    from app.models.edition import Edition
    from app.models.work import Work
    from app.services.covers import cover_service

    factory = get_session_factory()
    async with factory() as db:
        result = await db.execute(
            select(Edition)
            .where(Edition.id == edition_id)
            .options(joinedload(Edition.work).options(joinedload(Work.authors)))
        )
        edition = result.unique().scalar_one_or_none()
        if not edition:
            return {"status": "not_found"}

        title = edition.title
        isbn = edition.isbn
        author = edition.work.authors[0].name if edition.work and edition.work.authors else None

        itunes = await search_itunes_cover(isbn=isbn, title=title, author=author)
        if not itunes or not itunes.get("url"):
            return {"status": "no_match", "title": title}

        # Download the high-res cover
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                r = await client.get(itunes["url"], follow_redirects=True)
                if r.status_code != 200 or not r.content:
                    return {"status": "download_failed"}

            h, fmt, *_ = await cover_service.save_cover(r.content, edition.uuid)
            if h:
                edition.cover_hash = h
                edition.cover_format = fmt
                await db.commit()
                return {
                    "status": "upgraded",
                    "itunes_title": itunes["itunes_title"],
                    "itunes_author": itunes["itunes_author"],
                }
        except Exception as exc:
            logger.warning("Cover download failed for edition %d: %s", edition_id, exc)

    return {"status": "failed"}
