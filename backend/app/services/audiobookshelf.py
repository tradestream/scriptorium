"""AudiobookShelf integration service.

Connects to a self-hosted AudiobookShelf instance and:
- Fetches libraries and their items (audiobooks/ebooks)
- Syncs listening progress → Scriptorium ReadProgress
- Matches ABS items to existing Scriptorium books (by ISBN, ASIN, title+author)
- Imports new ABS items as Scriptorium book records
"""

import logging
from datetime import datetime
from typing import Any

import httpx

from app.config import get_settings
from app.services.covers import cover_service

logger = logging.getLogger("scriptorium.abs")

settings = get_settings()


class AudiobookShelfClient:
    """Thin async HTTP client for the AudiobookShelf REST API."""

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {api_key}"}

    async def _get(self, path: str, **params) -> Any:
        url = f"{self.base_url}{path}"
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(url, headers=self.headers, params=params or None)
            r.raise_for_status()
            return r.json()

    async def ping(self) -> bool:
        """Return True if the server is reachable and the key is valid."""
        try:
            data = await self._get("/api/me")
            return bool(data.get("username"))
        except Exception:
            return False

    async def get_server_info(self) -> dict:
        """Return basic server + user info."""
        return await self._get("/api/me")

    async def get_libraries(self) -> list[dict]:
        """Return all libraries."""
        data = await self._get("/api/libraries")
        return data.get("libraries", [])

    async def get_library_items(self, library_id: str, limit: int = 0) -> list[dict]:
        """Return all items in a library (paginated internally)."""
        items: list[dict] = []
        page = 0
        page_size = 100
        while True:
            data = await self._get(
                f"/api/libraries/{library_id}/items",
                limit=page_size,
                page=page,
                sort="addedAt",
                desc=0,
                filter="all",
                collapseseries=0,
            )
            batch = data.get("results", [])
            items.extend(batch)
            if len(items) >= data.get("total", 0) or not batch:
                break
            if limit and len(items) >= limit:
                break
            page += 1
        return items

    async def get_me_progress(self) -> list[dict]:
        """Return all in-progress media items for the authenticated user."""
        data = await self._get("/api/me/items-in-progress")
        return data.get("libraryItems", [])

    async def get_user_listening_sessions(self, user_id: str | None = None) -> list[dict]:
        """Return listening history sessions for a user (default: current user)."""
        uid = user_id or "me"
        try:
            data = await self._get(f"/api/users/{uid}/listening-sessions", itemsPerPage=100)
            return data.get("sessions", [])
        except Exception:
            return []

    async def get_item(self, item_id: str) -> dict:
        """Return a single library item by ID."""
        return await self._get(f"/api/items/{item_id}", expanded=1)


async def _fetch_abs_cover(client: "AudiobookShelfClient", abs_item_id: str) -> bytes | None:
    """Fetch cover bytes for an ABS item; returns None on any failure."""
    try:
        url = f"{client.base_url}/api/items/{abs_item_id}/cover"
        async with httpx.AsyncClient(timeout=20) as http:
            r = await http.get(url, headers=client.headers, follow_redirects=True)
            if r.status_code == 200 and r.content:
                return r.content
    except Exception:
        pass
    return None


def _get_client() -> AudiobookShelfClient | None:
    s = get_settings()
    if not s.ABS_URL or not s.ABS_API_KEY:
        return None
    return AudiobookShelfClient(s.ABS_URL, s.ABS_API_KEY)


def _extract_metadata(item: dict) -> dict:
    """Normalise an ABS library item into a flat metadata dict."""
    media = item.get("media", {})
    meta = media.get("metadata", {})

    # Authors: ABS stores as list of {id, name} or as plain string authorName
    authors: list[str] = []
    for a in meta.get("authors", []):
        if isinstance(a, dict):
            authors.append(a.get("name", ""))
        elif isinstance(a, str):
            authors.append(a)
    if not authors and meta.get("authorName"):
        authors = [n.strip() for n in meta["authorName"].split(",") if n.strip()]

    # Narrators
    narrators: list[str] = []
    for n in meta.get("narrators", []):
        if isinstance(n, str):
            narrators.append(n)
    if not narrators and meta.get("narratorName"):
        narrators = [n.strip() for n in meta["narratorName"].split(",") if n.strip()]

    # Series
    series_name: str | None = None
    series_seq: str | None = None
    for s in meta.get("series", []):
        if isinstance(s, dict):
            series_name = s.get("name")
            series_seq = str(s.get("sequence", "")) or None
            break
    if not series_name and meta.get("seriesName"):
        series_name = meta["seriesName"]

    # Published date
    published_year = meta.get("publishedYear") or meta.get("publishedDate", "")
    published_date: datetime | None = None
    if published_year:
        try:
            published_date = datetime(int(str(published_year)[:4]), 1, 1)
        except (ValueError, TypeError):
            pass

    return {
        "abs_item_id": item.get("id", ""),
        "title": meta.get("title") or item.get("media", {}).get("metadata", {}).get("title", "Unknown"),
        "subtitle": meta.get("subtitle"),
        "description": meta.get("description"),
        "authors": [a for a in authors if a],
        "narrators": narrators,
        "series_name": series_name,
        "series_seq": series_seq,
        "isbn": meta.get("isbn") or meta.get("isbn13"),
        "asin": meta.get("asin"),
        "publisher": meta.get("publisher"),
        "language": meta.get("language"),
        "published_date": published_date,
        "genres": meta.get("genres", []),
        "tags": item.get("media", {}).get("tags", []),
        "duration": media.get("duration"),  # seconds
        "cover_path": item.get("coverPath"),
        "media_type": item.get("mediaType", "book"),
        "added_at": item.get("addedAt"),
        "updated_at": item.get("updatedAt"),
    }


def _progress_from_item(item: dict) -> dict | None:
    """Extract progress info from an ABS library item (when returned via /me/items-in-progress)."""
    progress = item.get("userMediaProgress")
    if not progress:
        return None
    return {
        "abs_item_id": progress.get("libraryItemId", item.get("id", "")),
        "current_time": progress.get("currentTime", 0),
        "duration": progress.get("duration", 0),
        "progress": progress.get("progress", 0.0),   # 0.0 – 1.0
        "is_finished": progress.get("isFinished", False),
        "started_at": progress.get("startedAt"),
        "finished_at": progress.get("finishedAt"),
        "last_update": progress.get("lastUpdate"),
    }


async def sync_covers(overwrite: bool = False) -> dict:
    """Fetch covers from ABS for all linked editions/books missing one.

    Checks Edition.abs_item_id first (new model), then falls back to
    Book.abs_item_id for legacy rows.

    Returns counts of updated/skipped/failed.
    """
    client = _get_client()
    if not client:
        return {"error": "AudiobookShelf not configured"}

    from sqlalchemy import select
    from app.database import get_session_factory
    from app.models.book import Book
    from app.models.edition import Edition

    factory = get_session_factory()
    async with factory() as db:
        updated = 0
        skipped = 0
        failed = 0

        # ── Editions (new model) ──────────────────────────────────────────────
        eq = select(Edition).where(Edition.abs_item_id.isnot(None))
        if not overwrite:
            eq = eq.where(Edition.cover_hash.is_(None))
        for edition in (await db.execute(eq)).scalars().all():
            cover_bytes = await _fetch_abs_cover(client, edition.abs_item_id)
            if not cover_bytes:
                failed += 1
                continue
            h, fmt = await cover_service.save_cover(cover_bytes, edition.uuid)
            if h:
                edition.cover_hash = h
                edition.cover_format = fmt
                updated += 1
            else:
                failed += 1

        # ── Legacy Books (transition compat) ──────────────────────────────────
        bq = select(Book).where(Book.abs_item_id.isnot(None))
        if not overwrite:
            bq = bq.where(Book.cover_hash.is_(None))
        for book in (await db.execute(bq)).scalars().all():
            cover_bytes = await _fetch_abs_cover(client, book.abs_item_id)
            if not cover_bytes:
                failed += 1
                continue
            h, fmt = await cover_service.save_cover(cover_bytes, book.uuid)
            if h:
                book.cover_hash = h
                book.cover_format = fmt
                updated += 1
            else:
                failed += 1

        await db.commit()

    return {"updated": updated, "skipped": skipped, "failed": failed}


async def sync_progress(db_user_id: int) -> dict:
    """Pull listening progress from ABS and upsert into Scriptorium UserEdition / ReadProgress.

    Prefers the new Edition/UserEdition model; falls back to legacy Book/ReadProgress
    for rows that haven't been migrated yet.

    Returns a summary dict with counts.
    """
    client = _get_client()
    if not client:
        return {"error": "AudiobookShelf not configured"}

    from sqlalchemy import select
    from app.database import get_session_factory
    from app.models.book import Book
    from app.models.edition import Edition, UserEdition
    from app.models.progress import ReadProgress

    updated = 0
    matched = 0
    skipped = 0

    try:
        in_progress = await client.get_me_progress()
    except Exception as exc:
        logger.error("ABS sync_progress fetch failed: %s", exc)
        return {"error": str(exc)}

    factory = get_session_factory()
    async with factory() as db:
        for item in in_progress:
            prog = _progress_from_item(item)
            if not prog:
                continue

            abs_id = prog["abs_item_id"]
            pct = round(prog["progress"] * 100, 1)
            status = "completed" if prog["is_finished"] else ("reading" if pct > 0 else "want_to_read")

            finished_dt: datetime | None = None
            if prog["finished_at"]:
                try:
                    finished_dt = datetime.utcfromtimestamp(int(prog["finished_at"]) / 1000)
                except (ValueError, TypeError):
                    pass

            started_dt: datetime | None = None
            if prog["started_at"]:
                try:
                    started_dt = datetime.utcfromtimestamp(int(prog["started_at"]) / 1000)
                except (ValueError, TypeError):
                    pass

            # ── Try Edition first (new model) ─────────────────────────────────
            edition = (await db.execute(
                select(Edition).where(Edition.abs_item_id == abs_id).limit(1)
            )).scalar_one_or_none()

            if edition:
                matched += 1
                ue = (await db.execute(
                    select(UserEdition).where(
                        UserEdition.user_id == db_user_id,
                        UserEdition.edition_id == edition.id,
                    )
                )).scalar_one_or_none()
                if ue is None:
                    ue = UserEdition(
                        user_id=db_user_id,
                        edition_id=edition.id,
                        status=status,
                        percentage=prog["progress"],
                        started_at=started_dt,
                        completed_at=finished_dt if prog["is_finished"] else None,
                    )
                    db.add(ue)
                else:
                    ue.status = status
                    ue.percentage = prog["progress"]
                    if started_dt and not ue.started_at:
                        ue.started_at = started_dt
                    if prog["is_finished"] and finished_dt:
                        ue.completed_at = finished_dt
                updated += 1
                continue

            # ── Fall back to legacy Book / ReadProgress ───────────────────────
            book = (await db.execute(
                select(Book).where(Book.abs_item_id == abs_id).limit(1)
            )).scalar_one_or_none()
            if not book:
                skipped += 1
                continue

            matched += 1
            rp = (await db.execute(
                select(ReadProgress).where(
                    ReadProgress.user_id == db_user_id,
                    ReadProgress.book_id == book.id,
                )
            )).scalar_one_or_none()
            if rp is None:
                rp = ReadProgress(
                    user_id=db_user_id,
                    book_id=book.id,
                    status=status,
                    percentage=prog["progress"],
                    started_at=started_dt,
                    completed_at=finished_dt if prog["is_finished"] else None,
                )
                db.add(rp)
            else:
                rp.status = status
                rp.percentage = prog["progress"]
                if started_dt and not rp.started_at:
                    rp.started_at = started_dt
                if prog["is_finished"] and finished_dt:
                    rp.completed_at = finished_dt
            updated += 1

        await db.commit()

    return {
        "items_from_abs": len(in_progress),
        "matched": matched,
        "updated": updated,
        "skipped_unlinked": skipped,
    }


async def import_library_items(
    library_id: str,
    scriptorium_library_id: int,
    db_user_id: int,
    limit: int = 0,
) -> dict:
    """Import ABS library items into Scriptorium as Work+Edition records.

    Items already linked via Edition.abs_item_id or Book.abs_item_id are skipped.
    Existing records are matched by ISBN or title+first-author; matched editions
    get abs_item_id set, matched books get linked and an Edition stub created.
    Completely new items create a Work + Edition + legacy Book stub.
    """
    client = _get_client()
    if not client:
        return {"error": "AudiobookShelf not configured"}

    from sqlalchemy import select, func as sqlfunc
    from app.database import get_session_factory
    from app.models import Library
    from app.models.book import Author, Book, Series
    from app.models.book import book_authors as ba_table, book_series as bs_table
    from app.models.edition import Edition
    from app.models.work import Work, work_series as ws_table
    import uuid as _uuid

    try:
        items = await client.get_library_items(library_id, limit=limit)
    except Exception as exc:
        logger.error("ABS import_library_items fetch failed: %s", exc)
        return {"error": str(exc)}

    created = 0
    linked = 0
    skipped = 0

    factory = get_session_factory()
    async with factory() as db:
        lib_result = await db.execute(
            select(Library).where(Library.id == scriptorium_library_id)
        )
        library = lib_result.scalar_one_or_none()
        if not library:
            return {"error": f"Library {scriptorium_library_id} not found"}

        for item in items:
            meta = _extract_metadata(item)
            abs_id = meta["abs_item_id"]

            # ── Already linked? ───────────────────────────────────────────────
            already_edition = await db.scalar(
                select(Edition.id).where(Edition.abs_item_id == abs_id).limit(1)
            )
            if already_edition:
                skipped += 1
                continue
            already_book = await db.scalar(
                select(Book.id).where(Book.abs_item_id == abs_id).limit(1)
            )
            if already_book:
                skipped += 1
                continue

            # ── Try to match an existing Edition by ISBN ──────────────────────
            edition: Edition | None = None
            if meta["isbn"]:
                edition = (await db.execute(
                    select(Edition).where(Edition.isbn == meta["isbn"]).limit(1)
                )).scalar_one_or_none()

            # ── Try to match an existing Book by ISBN ─────────────────────────
            book: Book | None = None
            if edition is None and meta["isbn"]:
                book = (await db.execute(
                    select(Book).where(Book.isbn == meta["isbn"]).limit(1)
                )).scalar_one_or_none()

            # ── Try title + first author against Book (fallback) ──────────────
            if edition is None and book is None and meta["authors"]:
                first_author = meta["authors"][0]
                author = (await db.execute(
                    select(Author).where(
                        sqlfunc.lower(Author.name) == first_author.lower()
                    ).limit(1)
                )).scalar_one_or_none()
                if author:
                    book = (await db.execute(
                        select(Book)
                        .join(ba_table, Book.id == ba_table.c.book_id)
                        .where(
                            ba_table.c.author_id == author.id,
                            sqlfunc.lower(Book.title) == meta["title"].lower(),
                        )
                        .limit(1)
                    )).scalar_one_or_none()

            cover_bytes = await _fetch_abs_cover(client, abs_id)

            if edition is not None:
                # Link abs_item_id to existing Edition
                edition.abs_item_id = abs_id
                if cover_bytes and not edition.cover_hash:
                    h, fmt = await cover_service.save_cover(cover_bytes, edition.uuid)
                    if h:
                        edition.cover_hash = h
                        edition.cover_format = fmt
                linked += 1

            elif book is not None:
                # Link abs_item_id to existing Book; also set on its Edition if one exists
                book.abs_item_id = abs_id
                if cover_bytes and not book.cover_hash:
                    h, fmt = await cover_service.save_cover(cover_bytes, book.uuid)
                    if h:
                        book.cover_hash = h
                        book.cover_format = fmt
                # Link the corresponding Edition if it shares the same uuid
                linked_edition = (await db.execute(
                    select(Edition).where(Edition.uuid == book.uuid).limit(1)
                )).scalar_one_or_none()
                if linked_edition and not linked_edition.abs_item_id:
                    linked_edition.abs_item_id = abs_id
                linked += 1

            else:
                # ── Create new Work + Edition + legacy Book stub ───────────────
                entity_uuid = str(_uuid.uuid4())

                cover_hash: str | None = None
                cover_fmt: str | None = None
                if cover_bytes:
                    cover_hash, cover_fmt = await cover_service.save_cover(cover_bytes, entity_uuid)

                # Resolve or create authors
                authors = []
                for author_name in (meta["authors"] or []):
                    if not author_name:
                        continue
                    a = (await db.execute(
                        select(Author).where(Author.name == author_name).limit(1)
                    )).scalar_one_or_none()
                    if not a:
                        a = Author(name=author_name)
                        db.add(a)
                        await db.flush()
                    authors.append(a)

                # Work
                work = Work(
                    uuid=entity_uuid,
                    title=meta["title"],
                    subtitle=meta["subtitle"],
                    description=meta["description"],
                    language=meta["language"],
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                    authors=authors,
                )
                db.add(work)
                await db.flush()

                # Series (Work-level)
                if meta["series_name"]:
                    series = (await db.execute(
                        select(Series).where(Series.name == meta["series_name"]).limit(1)
                    )).scalar_one_or_none()
                    if not series:
                        series = Series(name=meta["series_name"])
                        db.add(series)
                        await db.flush()
                    seq: float | None = None
                    if meta["series_seq"]:
                        try:
                            seq = float(meta["series_seq"])
                        except (ValueError, TypeError):
                            pass
                    await db.execute(
                        ws_table.insert().values(work_id=work.id, series_id=series.id, position=seq)
                    )

                # Edition (audiobook stub — no files, format="audiobook")
                edition = Edition(
                    uuid=entity_uuid,
                    work_id=work.id,
                    library_id=scriptorium_library_id,
                    isbn=meta["isbn"],
                    publisher=meta["publisher"],
                    published_date=meta["published_date"],
                    language=meta["language"],
                    format="audiobook",
                    cover_hash=cover_hash,
                    cover_format=cover_fmt,
                    abs_item_id=abs_id,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                db.add(edition)
                await db.flush()

                # Legacy Book stub (transition compat)
                book = Book(
                    uuid=entity_uuid,
                    title=meta["title"],
                    subtitle=meta["subtitle"],
                    description=meta["description"],
                    isbn=meta["isbn"],
                    publisher=meta["publisher"],
                    language=meta["language"],
                    published_date=meta["published_date"],
                    cover_hash=cover_hash,
                    cover_format=cover_fmt,
                    library_id=scriptorium_library_id,
                    work_id=work.id,
                    abs_item_id=abs_id,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                    authors=authors,
                )
                db.add(book)
                await db.flush()

                # Series on legacy Book as well
                if meta["series_name"] and series:
                    await db.execute(
                        bs_table.insert().values(book_id=book.id, series_id=series.id)
                    )

                created += 1

        await db.commit()

    return {
        "total_abs_items": len(items),
        "created": created,
        "linked": linked,
        "skipped_already_linked": skipped,
    }
