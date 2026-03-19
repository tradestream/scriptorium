"""Kobo device sync service.

Implements the reverse-engineered Kobo store sync protocol so Kobo e-readers
can sync their library, reading progress, and bookmarks with Scriptorium
instead of Kobo's official cloud.

The protocol uses URL-path-based auth tokens (not headers) and exchanges JSON
payloads that mirror the Kobo storeapi.kobo.com responses.

References:
  - Calibre-Web kobo.py (most mature Python implementation)
  - Komga Kobo sync
  - BookLore Kobo integration
"""

import logging
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import and_, select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.models import Book, BookFile, Edition, EditionFile, Library, User, UserEdition, Work
from app.models.progress import (
    Device,
    KoboBookState,
    KoboShelfArchive,
    KoboSyncedBook,
    KoboSyncToken,
    KoboTokenShelf,
    ReadProgress,
)
from app.models.shelf import Shelf, ShelfBook

logger = logging.getLogger(__name__)

# Number of books per sync page (Kobo devices expect pagination)
SYNC_PAGE_SIZE = 100


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _kobo_timestamp(dt: Optional[datetime]) -> Optional[str]:
    """Format datetime as Kobo-compatible ISO 8601 string."""
    if dt is None:
        return None
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Token Management
# ---------------------------------------------------------------------------

async def generate_sync_token(
    user_id: int,
    db: AsyncSession,
    device_id: Optional[int] = None,
    shelf_ids: Optional[list[int]] = None,
) -> KoboSyncToken:
    """Generate a new Kobo sync auth token for a user."""
    token_str = secrets.token_hex(32)

    sync_token = KoboSyncToken(
        user_id=user_id,
        device_id=device_id,
        token=token_str,
        is_active=True,
    )
    db.add(sync_token)
    await db.flush()

    if shelf_ids:
        for sid in shelf_ids:
            db.add(KoboTokenShelf(token_id=sync_token.id, shelf_id=sid))

    await db.commit()
    await db.refresh(sync_token)
    return sync_token


async def validate_sync_token(
    token: str,
    db: AsyncSession,
) -> Optional[KoboSyncToken]:
    """Validate a Kobo sync token and return it if active."""
    stmt = select(KoboSyncToken).where(
        KoboSyncToken.token == token,
        KoboSyncToken.is_active == True,
    )
    result = await db.execute(stmt)
    sync_token = result.scalar_one_or_none()

    if sync_token:
        sync_token.last_used = _utcnow()
        await db.commit()

    return sync_token


async def revoke_sync_token(token_id: int, db: AsyncSession) -> bool:
    """Revoke (deactivate) a sync token."""
    stmt = select(KoboSyncToken).where(KoboSyncToken.id == token_id)
    result = await db.execute(stmt)
    sync_token = result.scalar_one_or_none()
    if sync_token:
        sync_token.is_active = False
        await db.commit()
        return True
    return False


async def list_user_sync_tokens(
    user_id: int,
    db: AsyncSession,
) -> list[KoboSyncToken]:
    """List all sync tokens for a user."""
    stmt = select(KoboSyncToken).where(
        KoboSyncToken.user_id == user_id
    ).order_by(KoboSyncToken.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

def build_initialization_response(auth_token: str, base_url: str) -> dict:
    """Build the /v1/initialization response."""
    kobo_base = f"{base_url}/kobo/{auth_token}"

    return {
        "Resources": {
            "library_sync": f"{kobo_base}/v1/library/sync",
            "library_items": f"{kobo_base}/v1/library/{{ItemId}}",
            "book": f"{kobo_base}/v1/library/{{ItemId}}/metadata",
            "reading_state": f"{kobo_base}/v1/library/{{ItemId}}/state",
            "content_url": f"{kobo_base}/v1/library/{{ItemId}}/download",
            "content_access_book": f"{kobo_base}/v1/library/{{ItemId}}/download/{{Type}}",
            "image_host": base_url,
            "image_url_quality_template": (
                f"{base_url}/covers/{{ImageId}}/{{Width}}/{{Height}}"
                "/false/image.jpg"
            ),
            "image_url_template": f"{base_url}/covers/{{ImageId}}/image.jpg",
            "tags": f"{kobo_base}/v1/library/tags",
            "affiliate": "",
            "deals": "",
            "featured": "",
            "stacks": "",
        }
    }


# ---------------------------------------------------------------------------
# Library Sync — Edition-first
# ---------------------------------------------------------------------------

async def get_sync_payload(
    sync_token: KoboSyncToken,
    db: AsyncSession,
    base_url: str,
) -> tuple[list[dict], bool]:
    """Build the /v1/library/sync response payload.

    Queries Edition rows (joined to their Work for metadata).
    Falls back to Book rows for instances that haven't been migrated yet.
    """
    user_id = sync_token.user_id

    # Resolve shelves to sync: token-attached shelves + all user shelves with sync_to_kobo=True
    shelf_rows = await db.execute(
        select(KoboTokenShelf.shelf_id).where(KoboTokenShelf.token_id == sync_token.id)
    )
    token_shelf_ids = [row[0] for row in shelf_rows]

    # Also include any shelf the user has flagged for Kobo sync
    from app.models.shelf import Shelf
    kobo_shelf_rows = await db.execute(
        select(Shelf.id).where(Shelf.user_id == user_id, Shelf.sync_to_kobo == True)
    )
    kobo_sync_ids = [row[0] for row in kobo_shelf_rows]
    # Merge: union of token shelves and sync_to_kobo shelves
    token_shelf_ids = list(set(token_shelf_ids + kobo_sync_ids))

    # Query editions joined to their work
    stmt = (
        select(Edition)
        .join(Library, Edition.library_id == Library.id)
        .where(Library.is_hidden == False)
        .options(
            selectinload(Edition.files),
            selectinload(Edition.work).options(
                selectinload(Work.authors),
                selectinload(Work.series),
            ),
        )
        .order_by(Edition.updated_at.desc())
    )

    # Shelf filter: include editions whose work is on one of the token's shelves.
    # Only apply if the shelves actually have books — otherwise sync everything
    # from visible libraries (the pre-shelf-filter behavior).
    if token_shelf_ids:
        has_books = await db.scalar(
            select(ShelfBook.id).where(ShelfBook.shelf_id.in_(token_shelf_ids)).limit(1)
        )
        if has_books:
            stmt = stmt.where(
                select(ShelfBook.work_id)
                .where(
                    ShelfBook.work_id == Edition.work_id,
                    ShelfBook.shelf_id.in_(token_shelf_ids),
                )
                .exists()
        )

    if sync_token.books_last_modified:
        # Incremental: only books changed since last sync
        stmt = stmt.where(Edition.updated_at > sync_token.books_last_modified)
    else:
        # Initial sync: exclude books already sent (KoboSyncedBooks lookup)
        stmt = stmt.where(
            ~select(KoboSyncedBook.id)
            .where(
                KoboSyncedBook.sync_token_id == sync_token.id,
                KoboSyncedBook.edition_id == Edition.id,
            )
            .exists()
        )

    stmt = stmt.limit(SYNC_PAGE_SIZE + 1)

    result = await db.execute(stmt)
    editions = list(result.scalars().all())

    has_more = len(editions) > SYNC_PAGE_SIZE
    if has_more:
        editions = editions[:SYNC_PAGE_SIZE]

    # Load KoboBookStates for these editions
    edition_ids = [e.id for e in editions]
    states_map: dict[int, KoboBookState] = {}
    if edition_ids:
        states_result = await db.execute(
            select(KoboBookState).where(
                KoboBookState.user_id == user_id,
                KoboBookState.edition_id.in_(edition_ids),
            )
        )
        for state in states_result.scalars().all():
            states_map[state.edition_id] = state

    is_incremental = bool(sync_token.books_last_modified)

    items = []
    for edition in editions:
        epub_file = _get_kobo_compatible_file_edition(edition.files)
        if not epub_file:
            continue

        state = states_map.get(edition.id)
        entry = _build_edition_entry(
            edition=edition,
            edition_file=epub_file,
            state=state,
            auth_token=sync_token.token,
            base_url=base_url,
            is_new=not is_incremental,
        )
        items.append(entry)

        if is_incremental and state:
            items.append({
                "ChangedReadingState": {
                    "ReadingState": _build_reading_state(edition.uuid, state)
                }
            })

    # Record synced editions in lookup table (Calibre-Web pattern)
    if editions:
        sync_token.books_last_modified = max(e.updated_at for e in editions)
        for edition in editions:
            # Upsert: skip if already recorded
            existing = await db.execute(
                select(KoboSyncedBook.id).where(
                    KoboSyncedBook.sync_token_id == sync_token.id,
                    KoboSyncedBook.edition_id == edition.id,
                )
            )
            if not existing.scalar_one_or_none():
                db.add(KoboSyncedBook(
                    sync_token_id=sync_token.id,
                    edition_id=edition.id,
                ))

    # ── Shelf tags (appear as collections on the Kobo device) ─────────────
    # Build a mapping of edition UUID → shelf names for tagged books
    if token_shelf_ids and editions:
        work_ids = [e.work_id for e in editions]
        shelf_book_rows = await db.execute(
            select(ShelfBook.work_id, Shelf.name)
            .join(Shelf, Shelf.id == ShelfBook.shelf_id)
            .where(ShelfBook.shelf_id.in_(token_shelf_ids), ShelfBook.work_id.in_(work_ids))
        )
        # Map work_id → list of shelf names
        work_shelves: dict[int, list[str]] = {}
        for wid, sname in shelf_book_rows:
            work_shelves.setdefault(wid, []).append(sname)

        # Build tag entries for each shelf
        seen_tags: set[str] = set()
        for edition in editions:
            shelf_names = work_shelves.get(edition.work_id, [])
            for sname in shelf_names:
                tag_id = f"SC-{sname.replace(' ', '-')}"
                if tag_id not in seen_tags:
                    seen_tags.add(tag_id)
                    items.append({
                        "NewTag": {
                            "Tag": {
                                "Created": edition.created_at.isoformat() + "Z" if edition.created_at else None,
                                "Id": tag_id,
                                "Items": [
                                    {"RevisionId": e.uuid, "Type": "ProductRevisionTagItem"}
                                    for e in editions
                                    if sname in work_shelves.get(e.work_id, [])
                                ],
                                "LastModified": edition.updated_at.isoformat() + "Z" if edition.updated_at else None,
                                "Name": sname,
                                "Type": "UserTag",
                            }
                        }
                    })

    await db.commit()
    return items, has_more


def _get_kobo_compatible_file_edition(files: list[EditionFile]) -> Optional[EditionFile]:
    """Find the best Kobo-compatible file from an edition's files."""
    priority = {"kepub": 0, "epub": 1, "pdf": 2}
    compatible = [f for f in files if f.format.lower() in priority]
    if not compatible:
        return None
    return sorted(compatible, key=lambda f: priority.get(f.format.lower(), 99))[0]


def _get_kobo_compatible_file(files: list[BookFile]) -> Optional[BookFile]:
    """Legacy: find the best Kobo-compatible file from a book's files."""
    priority = {"kepub": 0, "epub": 1, "pdf": 2}
    compatible = [f for f in files if f.format.lower() in priority]
    if not compatible:
        return None
    return sorted(compatible, key=lambda f: priority.get(f.format.lower(), 99))[0]


def _build_edition_entry(
    edition: Edition,
    edition_file: EditionFile,
    state: Optional[KoboBookState],
    auth_token: str,
    base_url: str,
    is_new: bool = True,
) -> dict:
    """Build a single Kobo library sync entry for an Edition."""
    kobo_base = f"{base_url}/kobo/{auth_token}"
    work = edition.work

    author_name = ""
    if work and work.authors:
        author_name = ", ".join(a.name for a in work.authors)

    series_name = None
    series_number = None
    if work and work.series:
        series_name = work.series[0].name

    envelope_key = "NewEntitlement" if is_new else "ChangedEntitlement"

    entry: dict[str, Any] = {
        envelope_key: {
            "BookEntitlement": {
                "Accessibility": "Full",
                "ActivePeriod": {"From": _kobo_timestamp(edition.created_at)},
                "Created": _kobo_timestamp(edition.created_at),
                "CrossRevisionId": edition.uuid,
                "Id": edition.uuid,
                "IsHiddenFromArchive": False,
                "IsLocked": False,
                "IsRemoved": False,
                "LastModified": _kobo_timestamp(edition.updated_at),
                "OriginCategory": "Imported",
                "RevisionId": edition.uuid,
                "Status": "Active",
            },
            "BookMetadata": {
                "Categories": [],
                "ContributorRoles": [
                    {"Name": author_name, "Role": "Author"}
                ] if author_name else [],
                "Contributors": author_name,
                "CoverImageId": edition.uuid if edition.cover_hash else None,
                "CrossRevisionId": edition.uuid,
                "CurrentDisplayPrice": {"CurrencyCode": "USD", "TotalAmount": 0},
                "Description": (work.description if work else None) or "",
                "DownloadUrls": [
                    {
                        "DrmType": "None",
                        "Format": edition_file.format.upper(),
                        "Size": edition_file.file_size,
                        "Url": f"{kobo_base}/v1/library/{edition.uuid}/download/{edition_file.format.lower()}",
                        "Platform": "Generic",
                    }
                ],
                "EntitlementId": edition.uuid,
                "ExternalIds": [],
                "Genre": "00000000-0000-0000-0000-000000000001",
                "IsEligibleForKoboLove": False,
                "IsInternetArchive": False,
                "IsPreOrder": False,
                "IsSocialEnabled": True,
                "Language": edition.language or (work.language if work else None) or "en",
                "PhoneticPronunciations": {},
                "PublicationDate": _kobo_timestamp(edition.published_date),
                "Publisher": {"Name": edition.publisher or ""},
                "RevisionId": edition.uuid,
                "Title": work.title if work else edition.uuid,
                "WorkId": edition.uuid,
            },
        }
    }

    if series_name:
        entry[envelope_key]["BookMetadata"]["Series"] = {
            "Name": series_name,
            "Number": str(series_number) if series_number else "0",
            "NumberFloat": float(series_number) if series_number else 0.0,
            "Id": series_name,
        }

    if state and is_new:
        entry[envelope_key]["ReadingState"] = _build_reading_state(edition.uuid, state)

    return entry


def _build_book_entry(
    book: Book,
    book_file: BookFile,
    state: Optional[KoboBookState],
    auth_token: str,
    base_url: str,
    is_new: bool = True,
) -> dict:
    """Legacy: build a Kobo entry from a Book record (used until migration 0034)."""
    kobo_base = f"{base_url}/kobo/{auth_token}"

    author_name = ""
    if book.authors:
        author_name = ", ".join(a.name for a in book.authors)

    series_name = None
    series_number = None
    if book.series:
        series_name = book.series[0].name

    envelope_key = "NewEntitlement" if is_new else "ChangedEntitlement"

    entry: dict[str, Any] = {
        envelope_key: {
            "BookEntitlement": {
                "Accessibility": "Full",
                "ActivePeriod": {"From": _kobo_timestamp(book.created_at)},
                "Created": _kobo_timestamp(book.created_at),
                "CrossRevisionId": book.uuid,
                "Id": book.uuid,
                "IsHiddenFromArchive": False,
                "IsLocked": False,
                "IsRemoved": False,
                "LastModified": _kobo_timestamp(book.updated_at),
                "OriginCategory": "Imported",
                "RevisionId": book.uuid,
                "Status": "Active",
            },
            "BookMetadata": {
                "Categories": [],
                "ContributorRoles": [
                    {"Name": author_name, "Role": "Author"}
                ] if author_name else [],
                "Contributors": author_name,
                "CoverImageId": book.uuid if book.cover_hash else None,
                "CrossRevisionId": book.uuid,
                "CurrentDisplayPrice": {"CurrencyCode": "USD", "TotalAmount": 0},
                "Description": book.description or "",
                "DownloadUrls": [
                    {
                        "DrmType": "None",
                        "Format": book_file.format.upper(),
                        "Size": book_file.file_size,
                        "Url": f"{kobo_base}/v1/library/{book.uuid}/download/{book_file.format.lower()}",
                        "Platform": "Generic",
                    }
                ],
                "EntitlementId": book.uuid,
                "ExternalIds": [],
                "Genre": "00000000-0000-0000-0000-000000000001",
                "IsEligibleForKoboLove": False,
                "IsInternetArchive": False,
                "IsPreOrder": False,
                "IsSocialEnabled": True,
                "Language": book.language or "en",
                "PhoneticPronunciations": {},
                "PublicationDate": _kobo_timestamp(book.published_date),
                "Publisher": {"Name": ""},
                "RevisionId": book.uuid,
                "Title": book.title,
                "WorkId": book.uuid,
            },
        }
    }

    if series_name:
        entry[envelope_key]["BookMetadata"]["Series"] = {
            "Name": series_name,
            "Number": str(series_number) if series_number else "0",
            "NumberFloat": float(series_number) if series_number else 0.0,
            "Id": series_name,
        }

    if state and is_new:
        entry[envelope_key]["ReadingState"] = _build_reading_state(book.uuid, state)

    return entry


def _build_reading_state(entity_uuid: str, state: KoboBookState) -> dict:
    """Build the Kobo ReadingState object from our stored state."""
    return {
        "EntitlementId": entity_uuid,
        "Created": _kobo_timestamp(state.created_at),
        "LastModified": _kobo_timestamp(state.updated_at),
        "PriorityTimestamp": _kobo_timestamp(state.updated_at),
        "StatusInfo": {
            "LastModified": _kobo_timestamp(state.updated_at),
            "Status": state.status,
            "TimesStartedReading": state.times_started_reading,
        },
        "Statistics": {
            "SpentReadingMinutes": state.time_spent_reading // 60,
            "RemainingTimeMinutes": 0,
        },
        "CurrentBookmark": {
            "ContentSourceProgressPercent": state.content_source_progress,
            "Location": {
                "Source": state.content_id or "",
                "Type": "KoboSpan",
                "Value": f"spine#{state.spine_index}",
            },
            "ProgressPercent": state.content_source_progress,
        },
    }


# ---------------------------------------------------------------------------
# Reading State Updates (device → server)
# ---------------------------------------------------------------------------

async def update_reading_state(
    book_uuid: str,
    user_id: int,
    state_data: dict,
    db: AsyncSession,
) -> Optional[KoboBookState]:
    """Process a reading state update from a Kobo device.

    Looks up by UUID (which is identical on both Edition and Book rows during
    the transition period). Prefers Edition; falls back to Book.
    Updates KoboBookState and UserEdition (the canonical user reading state).
    """
    # Try Edition first
    edition_stmt = select(Edition).where(Edition.uuid == book_uuid)
    edition_result = await db.execute(edition_stmt)
    edition = edition_result.scalar_one_or_none()

    book_id: Optional[int] = None
    edition_id: Optional[int] = None

    if edition:
        edition_id = edition.id
    else:
        # Fall back to legacy Book row
        book_stmt = select(Book).where(Book.uuid == book_uuid)
        book_result = await db.execute(book_stmt)
        book = book_result.scalar_one_or_none()
        if not book:
            logger.warning("Reading state update for unknown UUID: %s", book_uuid)
            return None
        book_id = book.id

    # Upsert KoboBookState
    if edition_id is not None:
        state_stmt = select(KoboBookState).where(
            KoboBookState.user_id == user_id,
            KoboBookState.edition_id == edition_id,
        )
    else:
        state_stmt = select(KoboBookState).where(
            KoboBookState.user_id == user_id,
            KoboBookState.edition_id == book_id,
        )

    state_result = await db.execute(state_stmt)
    kobo_state = state_result.scalar_one_or_none()

    if not kobo_state:
        kobo_state = KoboBookState(
            user_id=user_id,
            edition_id=book_id,
        )
        db.add(kobo_state)

    status_info = state_data.get("StatusInfo", {})
    if "Status" in status_info:
        kobo_state.status = status_info["Status"]
    if "TimesStartedReading" in status_info:
        kobo_state.times_started_reading = status_info["TimesStartedReading"]

    statistics = state_data.get("Statistics", {})
    if "SpentReadingMinutes" in statistics:
        kobo_state.time_spent_reading = statistics["SpentReadingMinutes"] * 60

    bookmark = state_data.get("CurrentBookmark", {})

    is_finished = kobo_state.status == "Finished"
    if not is_finished:
        if "ContentSourceProgressPercent" in bookmark:
            kobo_state.content_source_progress = bookmark["ContentSourceProgressPercent"]
        elif "ProgressPercent" in bookmark:
            kobo_state.content_source_progress = bookmark["ProgressPercent"]

        location = bookmark.get("Location", {})
        if location.get("Source"):
            kobo_state.content_id = location["Source"]
        val = location.get("Value", "")
        if val.startswith("spine#"):
            try:
                kobo_state.spine_index = int(val[6:])
            except ValueError:
                pass
    else:
        kobo_state.content_source_progress = 100.0

    kobo_state.updated_at = _utcnow()

    # Sync to UserEdition (primary) and legacy ReadProgress (compat)
    if edition_id is not None:
        await _sync_to_user_edition(user_id=user_id, edition_id=edition_id, kobo_state=kobo_state, db=db)
    if book_id is not None:
        await _sync_to_read_progress(user_id=user_id, edition_id=book_id, kobo_state=kobo_state, db=db)

    await db.commit()
    await db.refresh(kobo_state)
    return kobo_state


async def _sync_to_user_edition(
    user_id: int,
    edition_id: int,
    kobo_state: KoboBookState,
    db: AsyncSession,
) -> None:
    """Sync Kobo reading state into the UserEdition table."""
    from app.models.edition import UserEdition

    stmt = select(UserEdition).where(
        UserEdition.user_id == user_id,
        UserEdition.edition_id == edition_id,
    )
    result = await db.execute(stmt)
    ue = result.scalar_one_or_none()

    if not ue:
        ue = UserEdition(user_id=user_id, edition_id=edition_id)
        db.add(ue)

    status_map = {
        "ReadyToRead": "want_to_read",
        "Reading": "reading",
        "Finished": "completed",
    }
    ue.status = status_map.get(kobo_state.status, "reading")
    ue.percentage = kobo_state.content_source_progress
    ue.current_page = kobo_state.current_page
    if kobo_state.total_pages:
        ue.total_pages = kobo_state.total_pages
    ue.last_opened = _utcnow()

    if ue.status == "completed" and not ue.completed_at:
        ue.completed_at = _utcnow()
    if kobo_state.times_started_reading > 0 and not ue.started_at:
        ue.started_at = _utcnow()


async def _sync_to_read_progress(
    user_id: int,
    book_id: int,
    kobo_state: KoboBookState,
    db: AsyncSession,
) -> None:
    """Legacy: sync Kobo reading state into ReadProgress (kept for transition)."""
    stmt = select(ReadProgress).where(
        ReadProgress.user_id == user_id,
        ReadProgress.edition_id == book_id,
    )
    result = await db.execute(stmt)
    progress = result.scalar_one_or_none()

    if not progress:
        device = await _get_or_create_kobo_device(user_id, db)
        progress = ReadProgress(
            user_id=user_id,
            edition_id=book_id,
            device_id=device.id,
        )
        db.add(progress)

    status_map = {
        "ReadyToRead": "reading",
        "Reading": "reading",
        "Finished": "completed",
    }
    progress.status = status_map.get(kobo_state.status, "reading")
    progress.percentage = kobo_state.content_source_progress
    progress.current_page = kobo_state.current_page
    if kobo_state.total_pages:
        progress.total_pages = kobo_state.total_pages
    progress.last_opened = _utcnow()

    if progress.status == "completed" and not progress.completed_at:
        progress.completed_at = _utcnow()
    if kobo_state.times_started_reading > 0 and not progress.started_at:
        progress.started_at = _utcnow()


async def _get_or_create_kobo_device(
    user_id: int,
    db: AsyncSession,
) -> Device:
    """Get or create a generic Kobo device record for a user."""
    stmt = select(Device).where(
        Device.user_id == user_id,
        Device.device_type == "kobo",
    )
    result = await db.execute(stmt)
    device = result.scalar_one_or_none()

    if not device:
        device = Device(
            user_id=user_id,
            name="Kobo eReader",
            device_type="kobo",
        )
        db.add(device)
        await db.flush()

    return device


# ---------------------------------------------------------------------------
# Book Download — Edition-first
# ---------------------------------------------------------------------------

async def get_download_path(
    book_uuid: str,
    file_format: str,
    db: AsyncSession,
) -> Optional[Path]:
    """Get the filesystem path for a file to serve to a Kobo device.

    Checks EditionFile first (new), then falls back to BookFile (legacy).
    """
    # Try EditionFile via Edition.uuid
    stmt = (
        select(EditionFile)
        .join(Edition, EditionFile.edition_id == Edition.id)
        .where(
            Edition.uuid == book_uuid,
            EditionFile.format == file_format,
        )
    )
    result = await db.execute(stmt)
    edition_file = result.scalar_one_or_none()

    if edition_file:
        from app.config import resolve_path

        # Auto-convert EPUB to KEPUB for better Kobo experience
        if file_format.lower() in ("epub", "kepub") and edition_file.format.lower() == "epub":
            try:
                from app.services.kepub import ensure_kepub
                kepub_path = await ensure_kepub(edition_file)
                if kepub_path:
                    resolved = Path(resolve_path(kepub_path))
                    if resolved.exists():
                        await db.commit()  # persist kepub_path/hash on edition_file
                        return resolved
            except Exception:
                pass  # Fall through to original file

        path = Path(resolve_path(edition_file.file_path))
        return path if path.exists() else None

    # Fallback to legacy BookFile
    stmt = (
        select(BookFile)
        .join(Book, BookFile.edition_id == Book.id)
        .where(
            Book.uuid == book_uuid,
            BookFile.format == file_format,
        )
    )
    result = await db.execute(stmt)
    book_file = result.scalar_one_or_none()

    if not book_file:
        return None

    from app.config import resolve_path
    path = Path(resolve_path(book_file.file_path))
    return path if path.exists() else None


# ---------------------------------------------------------------------------
# Sync URL Builder (for settings page)
# ---------------------------------------------------------------------------

def build_sync_url(auth_token: str, base_url: str) -> str:
    """Build the api_endpoint value that users put in their Kobo device config."""
    return f"{base_url}/kobo/{auth_token}"
