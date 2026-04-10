"""Kobo sync API endpoints.

Implements the reverse-engineered Kobo store sync protocol. Kobo devices
communicate via URL-path-based auth tokens: /kobo/{auth_token}/v1/...

This router is mounted at the app root (NOT under /api/v1) because Kobo
devices expect the exact URL structure they're configured with.

Endpoints:
  GET  /kobo/{auth_token}/v1/initialization
  GET  /kobo/{auth_token}/v1/library/sync
  GET  /kobo/{auth_token}/v1/library/{book_uuid}/metadata
  GET  /kobo/{auth_token}/v1/library/{book_uuid}/state
  PUT  /kobo/{auth_token}/v1/library/{book_uuid}/state
  GET  /kobo/{auth_token}/v1/library/{book_uuid}/download/{format}
  GET  /kobo/{auth_token}/v1/library/tags

Management (under /api/v1, JWT-authed):
  POST   /api/v1/kobo/tokens          Generate a sync token
  GET    /api/v1/kobo/tokens          List user's sync tokens
  DELETE /api/v1/kobo/tokens/{id}     Revoke a sync token
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.models.progress import KoboSyncToken
from app.services.kobo_sync import (
    build_initialization_response,
    build_sync_url,
    generate_sync_token,
    get_download_path,
    get_sync_payload,
    list_user_sync_tokens,
    revoke_sync_token,
    update_reading_state,
    validate_sync_token,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Kobo device-facing router (URL-token auth, mounted at app root)
# ---------------------------------------------------------------------------
kobo_device_router = APIRouter()


async def _get_sync_token(
    auth_token: str,
    db: AsyncSession = Depends(get_db),
) -> KoboSyncToken:
    """Validate the URL-path auth token and return the sync token record."""
    sync_token = await validate_sync_token(auth_token, db)
    if not sync_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked sync token",
        )
    return sync_token


def _get_base_url(request: Request) -> str:
    """Extract the base URL from the incoming request for building absolute URLs.

    Checks X-Forwarded-Proto/Host headers from reverse proxy. Falls back to
    request scheme/host. Forces HTTPS if the host looks like a public domain
    (not localhost/IP) since Kobo devices require HTTPS for downloads.
    """
    scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.url.netloc)
    # Force HTTPS for non-local hosts (reverse proxy may not forward proto header)
    if scheme == "http" and host and not any(h in host for h in ("localhost", "127.0.0.1", "192.168.", "10.", "172.")):
        scheme = "https"
    return f"{scheme}://{host}"


@kobo_device_router.post("/kobo/{auth_token}/v1/auth/device")
async def kobo_auth_device(
    auth_token: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Kobo device auth endpoint.

    Called during initial setup and periodically by the device. We return a
    dummy token response — actual auth uses the URL-path token, not these tokens.
    """
    await _get_sync_token(auth_token, db)
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    import secrets as _secrets
    return {
        "AccessToken": _secrets.token_urlsafe(18),
        "RefreshToken": _secrets.token_urlsafe(18),
        "TokenType": "Bearer",
        "TrackingId": str(__import__("uuid").uuid4()),
        "UserKey": body.get("UserKey", ""),
    }


@kobo_device_router.get("/kobo/{auth_token}/v1/initialization")
async def kobo_initialization(
    auth_token: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Kobo initialization endpoint.

    Called first by the Kobo device to discover available API endpoints.
    Returns a Resources dictionary with URLs for all operations.
    The x-kobo-apitoken header (base64 of '{}') is required by the device.
    """
    sync_token = await _get_sync_token(auth_token, db)
    base_url = _get_base_url(request)
    payload = build_initialization_response(auth_token, base_url)
    return JSONResponse(content=payload, headers={"x-kobo-apitoken": "e30="})


@kobo_device_router.get("/kobo/{auth_token}/v1/library/sync")
async def kobo_library_sync(
    auth_token: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Main Kobo library sync endpoint.

    Returns books and reading state changes since the device's last sync.
    If there are more items than fit in one page, the response includes
    the X-Kobo-Sync: continue header and the device will call again.
    """
    sync_token = await _get_sync_token(auth_token, db)
    base_url = _get_base_url(request)

    items, has_more = await get_sync_payload(sync_token, db, base_url)

    # Build sync token for device to send back on next request
    import base64 as _b64
    import json as _json
    sync_state = {
        "last_modified": sync_token.books_last_modified.isoformat() if sync_token.books_last_modified else None,
        "token_id": sync_token.id,
    }
    sync_token_b64 = _b64.b64encode(_json.dumps(sync_state).encode()).decode()

    response = JSONResponse(
        content=items,
        media_type="application/json; charset=utf-8",
    )
    response.headers["x-kobo-sync"] = "continue" if has_more else ""
    response.headers["x-kobo-synctoken"] = sync_token_b64
    response.headers["x-kobo-apitoken"] = "e30="

    return response


@kobo_device_router.get("/kobo/{auth_token}/v1/library/{book_uuid}/metadata")
async def kobo_book_metadata(
    auth_token: str,
    book_uuid: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Get metadata for a specific book.

    The device calls this endpoint when the user taps a book to download
    it, or when it needs to refresh metadata for a synced entitlement.
    CWA returns the FULL BookMetadata here including DownloadUrls — the
    device uses this response to get the actual download URL. A minimal
    response without DownloadUrls causes the download to silently fail.
    """
    sync_token = await _get_sync_token(auth_token, db)

    from sqlalchemy.orm import selectinload
    from app.models import Book, Work
    from app.services.kobo_sync import (
        _build_edition_entry,
        _get_kobo_compatible_file_edition,
    )

    # Accept UUID or numeric id
    base = select(Book).options(
        selectinload(Book.work).selectinload(Work.authors),
        selectinload(Book.work).selectinload(Work.series),
        selectinload(Book.files),
    )
    stmt = base.where(Book.uuid == book_uuid)
    result = await db.execute(stmt)
    book = result.scalar_one_or_none()
    if book is None and book_uuid.isdigit():
        stmt = base.where(Book.id == int(book_uuid))
        result = await db.execute(stmt)
        book = result.scalar_one_or_none()

    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    epub_file = _get_kobo_compatible_file_edition(book.files)
    if not epub_file:
        raise HTTPException(status_code=404, detail="No compatible file")

    base_url = _get_base_url(request)
    entry = _build_edition_entry(
        edition=book,
        edition_file=epub_file,
        state=None,
        auth_token=sync_token.token,
        base_url=base_url,
        is_new=False,
    )

    # Extract BookMetadata from the entitlement envelope and return as
    # a JSON array (CWA convention — device expects a list).
    envelope = entry.get("ChangedEntitlement") or entry.get("NewEntitlement", {})
    metadata = envelope.get("BookMetadata", {})

    return JSONResponse(
        content=[metadata],
        media_type="application/json; charset=utf-8",
    )


@kobo_device_router.get("/kobo/{auth_token}/v1/library/{book_uuid}/state")
async def kobo_get_reading_state(
    auth_token: str,
    book_uuid: str,
    db: AsyncSession = Depends(get_db),
):
    """Get the reading state for a specific book."""
    sync_token = await _get_sync_token(auth_token, db)

    from app.models.progress import KoboBookState
    from app.services.kobo_sync import _build_reading_state, _find_edition_by_any_id

    book = await _find_edition_by_any_id(book_uuid, db)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    state_stmt = select(KoboBookState).where(
        KoboBookState.user_id == sync_token.user_id,
        KoboBookState.edition_id == book.id,
    )
    state_result = await db.execute(state_stmt)
    state = state_result.scalar_one_or_none()

    if not state:
        # Kobo expects a JSON array at this endpoint (confirmed by CWA).
        return [
            {
                "EntitlementId": book_uuid,
                "Created": None,
                "LastModified": None,
                "PriorityTimestamp": None,
                "StatusInfo": {"Status": "ReadyToRead", "TimesStartedReading": 0},
                "Statistics": {},
                "CurrentBookmark": {"ProgressPercent": 0},
            }
        ]

    return [_build_reading_state(book_uuid, state)]


@kobo_device_router.put("/kobo/{auth_token}/v1/library/{book_uuid}/state")
async def kobo_put_reading_state(
    auth_token: str,
    book_uuid: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Update the reading state for a specific book.

    Called by the Kobo device when the user reads, bookmarks, or finishes a book.
    We store the Kobo-specific state and also update our unified ReadProgress.
    """
    sync_token = await _get_sync_token(auth_token, db)
    body = await request.json()

    # Device sends { "ReadingStates": [ {...}, ... ] } — a PUT for a single
    # book may still contain multiple state fragments (bookmark + status +
    # stats). Process them all; CWA and grimmory both iterate.
    reading_states = body.get("ReadingStates") or [body]

    update_results = []
    any_success = False
    for state_data in reading_states:
        state = await update_reading_state(
            book_uuid=book_uuid,
            user_id=sync_token.user_id,
            state_data=state_data,
            db=db,
        )
        if state:
            any_success = True
            update_results.append(
                {
                    "EntitlementId": book_uuid,
                    "CurrentBookmarkResult": {"Result": "Success"},
                    "StatisticsResult": {"Result": "Success"},
                    "StatusInfoResult": {"Result": "Success"},
                }
            )

    if not any_success:
        raise HTTPException(status_code=404, detail="Book not found")

    return {
        "RequestResult": "Success",
        "UpdateResults": update_results,
    }


@kobo_device_router.get(
    "/kobo/{auth_token}/v1/library/{book_uuid}/download/{file_format}"
)
async def kobo_download_book(
    auth_token: str,
    book_uuid: str,
    file_format: str,
    db: AsyncSession = Depends(get_db),
):
    """Download a book file to the Kobo device.

    Serves the actual EPUB/KEPUB/PDF file for sideloading onto the device.
    """
    sync_token = await _get_sync_token(auth_token, db)

    file_path = await get_download_path(book_uuid, file_format, db)
    if not file_path:
        raise HTTPException(status_code=404, detail="Book file not found")

    media_types = {
        "epub": "application/epub+zip",
        "kepub": "application/kepub+zip",
        "pdf": "application/pdf",
    }
    media_type = media_types.get(file_format.lower(), "application/octet-stream")

    # Kobo resumes partial downloads via Range + ETag/Last-Modified, so
    # include both. ETag is based on (uuid, size, mtime) — stable enough
    # to dedupe but changes when the file is rewritten.
    import os
    stat = os.stat(file_path)
    etag = f'"{book_uuid}-{stat.st_size}-{int(stat.st_mtime)}"'
    last_modified = datetime.utcfromtimestamp(stat.st_mtime).strftime(
        "%a, %d %b %Y %H:%M:%S GMT"
    )

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=file_path.name,
        headers={
            "ETag": etag,
            "Last-Modified": last_modified,
            "Accept-Ranges": "bytes",
        },
    )


@kobo_device_router.get("/kobo/{auth_token}/v1/library/tags")
async def kobo_get_tags(
    auth_token: str,
    db: AsyncSession = Depends(get_db),
):
    """Get tags/shelves for the Kobo device.

    Maps our Shelf/Tag system to Kobo's collection format.
    """
    sync_token = await _get_sync_token(auth_token, db)

    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models.shelf import Shelf

    stmt = (
        select(Shelf)
        .where(Shelf.user_id == sync_token.user_id)
        .options(selectinload(Shelf.works))
    )
    result = await db.execute(stmt)
    shelves = result.unique().scalars().all()

    tags = []
    for shelf in shelves:
        created = shelf.created_at.strftime("%Y-%m-%dT%H:%M:%SZ") if shelf.created_at else None
        items = [
            {"RevisionId": work.uuid, "Type": "ProductRevisionTagItem"}
            for work in shelf.works
        ]
        tags.append({
            "Id": str(shelf.id),
            "Name": shelf.name,
            "Created": created,
            "Items": items,
            "Type": "UserTag",
        })

    return tags


# ---------------------------------------------------------------------------
# Bidirectional shelf sync — Kobo device creates/deletes tags
# ---------------------------------------------------------------------------

@kobo_device_router.post("/kobo/{auth_token}/v1/library/tags")
async def kobo_create_tag(
    auth_token: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Handle tag/collection creation from the Kobo device.

    Creates BOTH a Shelf (for Kobo sync) and a Collection (for browsing).
    Deduplicates by tag_id and name to prevent duplicates on repeated syncs.
    """
    sync_token = await _get_sync_token(auth_token, db)
    body = await request.json()

    tag_name = body.get("Name", "").strip()
    tag_id = body.get("Id", "")
    if not tag_name:
        return JSONResponse({"error": "No tag name"}, status_code=400)

    from sqlalchemy import select
    from app.models.shelf import Shelf
    from app.models.collection import Collection
    from app.models.progress import KoboShelfArchive

    # Check if we already have this tag mapped
    existing_archive = await db.execute(
        select(KoboShelfArchive).where(
            KoboShelfArchive.user_id == sync_token.user_id,
            KoboShelfArchive.kobo_tag_id == tag_id,
            KoboShelfArchive.is_deleted == False,
        )
    )
    if existing_archive.scalar_one_or_none():
        return {"Id": tag_id, "Name": tag_name, "Items": [], "Type": "UserTag"}

    # --- Shelf (for Kobo sync) ---
    existing_shelf = await db.execute(
        select(Shelf).where(Shelf.user_id == sync_token.user_id, Shelf.name == tag_name)
    )
    shelf = existing_shelf.scalar_one_or_none()
    if not shelf:
        shelf = Shelf(
            user_id=sync_token.user_id,
            name=tag_name,
            sync_to_kobo=True,
        )
        db.add(shelf)
        await db.flush()
    elif not shelf.sync_to_kobo:
        shelf.sync_to_kobo = True

    # --- Collection (for browsing) ---
    existing_col = await db.execute(
        select(Collection).where(Collection.user_id == sync_token.user_id, Collection.name == tag_name)
    )
    collection = existing_col.scalar_one_or_none()
    if not collection:
        collection = Collection(
            user_id=sync_token.user_id,
            name=tag_name,
            sync_to_kobo=True,
            source="kobo",
        )
        db.add(collection)
        await db.flush()

    # --- Archive mapping ---
    archive = KoboShelfArchive(
        user_id=sync_token.user_id,
        kobo_tag_id=tag_id or str(shelf.id),
        shelf_id=shelf.id,
        name=tag_name,
    )
    db.add(archive)
    await db.commit()

    logger.info("Kobo tag '%s' → shelf %d + collection %d", tag_name, shelf.id, collection.id)

    return {
        "Id": tag_id or str(shelf.id),
        "Name": tag_name,
        "Created": shelf.created_at.strftime("%Y-%m-%dT%H:%M:%SZ") if shelf.created_at else None,
        "Items": [],
        "Type": "UserTag",
    }


@kobo_device_router.delete("/kobo/{auth_token}/v1/library/tags/{tag_id}")
async def kobo_delete_tag(
    auth_token: str,
    tag_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Handle tag/collection deletion from the Kobo device.

    Soft-deletes the shelf archive entry. Optionally deletes the shelf.
    """
    sync_token = await _get_sync_token(auth_token, db)

    from app.models.progress import KoboShelfArchive
    from sqlalchemy import select

    result = await db.execute(
        select(KoboShelfArchive).where(
            KoboShelfArchive.user_id == sync_token.user_id,
            KoboShelfArchive.kobo_tag_id == tag_id,
        )
    )
    archive = result.scalar_one_or_none()
    if archive:
        archive.is_deleted = True
        logger.info("Kobo deleted tag '%s'", archive.name)
    await db.commit()

    return Response(status_code=204)


@kobo_device_router.put("/kobo/{auth_token}/v1/library/tags/{tag_id}/items")
async def kobo_add_items_to_tag(
    auth_token: str,
    tag_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Handle adding books to a tag from the Kobo device. Adds to both Shelf and Collection."""
    sync_token = await _get_sync_token(auth_token, db)
    body = await request.json()
    items = body.get("Items", [])

    from app.models.progress import KoboShelfArchive
    from app.models.shelf import ShelfBook
    from app.models.collection import Collection, CollectionBook

    result = await db.execute(
        select(KoboShelfArchive).where(
            KoboShelfArchive.user_id == sync_token.user_id,
            KoboShelfArchive.kobo_tag_id == tag_id,
        )
    )
    archive = result.scalar_one_or_none()
    if not archive:
        return Response(status_code=404)

    # Find matching collection
    col_result = await db.execute(
        select(Collection).where(Collection.user_id == sync_token.user_id, Collection.name == archive.name)
    )
    collection = col_result.scalar_one_or_none()

    for item in items:
        rev_id = item.get("RevisionId")
        if not rev_id:
            continue
        from app.services.kobo_sync import _find_edition_by_any_id
        edition = await _find_edition_by_any_id(str(rev_id), db)
        if not edition:
            continue

        # Add to shelf
        if archive.shelf_id:
            existing = await db.execute(
                select(ShelfBook.id).where(ShelfBook.shelf_id == archive.shelf_id, ShelfBook.work_id == edition.work_id)
            )
            if not existing.scalar_one_or_none():
                db.add(ShelfBook(shelf_id=archive.shelf_id, work_id=edition.work_id, position=0))

        # Add to collection
        if collection:
            existing = await db.execute(
                select(CollectionBook.id).where(CollectionBook.collection_id == collection.id, CollectionBook.work_id == edition.work_id)
            )
            if not existing.scalar_one_or_none():
                db.add(CollectionBook(collection_id=collection.id, work_id=edition.work_id, position=0))

    await db.commit()
    return Response(status_code=201)


@kobo_device_router.delete("/kobo/{auth_token}/v1/library/tags/{tag_id}/items/{item_id}")
async def kobo_remove_item_from_tag(
    auth_token: str,
    tag_id: str,
    item_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Handle removing a book from a tag on the Kobo device. Removes from both Shelf and Collection."""
    sync_token = await _get_sync_token(auth_token, db)

    from app.models.progress import KoboShelfArchive
    from app.models.shelf import ShelfBook
    from app.models.collection import Collection, CollectionBook

    result = await db.execute(
        select(KoboShelfArchive).where(
            KoboShelfArchive.user_id == sync_token.user_id,
            KoboShelfArchive.kobo_tag_id == tag_id,
        )
    )
    archive = result.scalar_one_or_none()
    if not archive:
        return Response(status_code=404)

    from app.services.kobo_sync import _find_edition_by_any_id
    edition = await _find_edition_by_any_id(item_id, db)
    if edition:
        # Remove from shelf
        if archive.shelf_id:
            sb = (await db.execute(
                select(ShelfBook).where(ShelfBook.shelf_id == archive.shelf_id, ShelfBook.work_id == edition.work_id)
            )).scalar_one_or_none()
            if sb:
                await db.delete(sb)

        # Remove from collection
        col = (await db.execute(
            select(Collection).where(Collection.user_id == sync_token.user_id, Collection.name == archive.name)
        )).scalar_one_or_none()
        if col:
            cb = (await db.execute(
                select(CollectionBook).where(CollectionBook.collection_id == col.id, CollectionBook.work_id == edition.work_id)
            )).scalar_one_or_none()
            if cb:
                await db.delete(cb)

    await db.commit()
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Koblime-style annotation sync — device pushes Bookmark table rows
# ---------------------------------------------------------------------------

@kobo_device_router.post("/kobo/{auth_token}/v1/annotations/sync")
async def kobo_sync_annotations(
    auth_token: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Receive a batch of Kobo Bookmark table rows from the device.

    Expected payload (Koblime format):
    {
        "bookmarks": [
            {
                "BookmarkID": "uuid",
                "VolumeID": "file:///mnt/onboard/...",
                "Text": "highlighted passage",
                "Annotation": "user note",
                "StartContainerPath": "OEBPS/chapter1.xhtml",
                "StartContainerChildIndex": 5,
                "StartOffset": 42,
                "EndContainerPath": "OEBPS/chapter1.xhtml",
                "EndContainerChildIndex": 5,
                "EndOffset": 120,
                "DateCreated": "2025-03-17T10:30:00Z",
                "DateModified": "2025-03-17T10:30:00Z",
                "ExtraAnnotationData": "{...}"
            }
        ],
        "device_id": "optional-device-identifier"
    }

    Also accepts the Content table for reading progress:
    {
        "content": [
            {
                "ContentID": "file:///mnt/onboard/...",
                "___PercentRead": 45.2,
                "TimeSpentReading": 3600
            }
        ]
    }
    """
    sync_token = await _get_sync_token(auth_token, db)
    body = await request.json()

    bookmarks = body.get("bookmarks", body.get("Bookmarks", []))
    device_id = body.get("device_id", body.get("DeviceId"))
    content_rows = body.get("content", body.get("Content", []))

    result = {"bookmarks": {}, "content": {}}

    # Sync bookmarks (highlights, notes, dogears)
    if bookmarks:
        from app.services.kobo_annotations import sync_bookmarks
        result["bookmarks"] = await sync_bookmarks(
            user_id=sync_token.user_id,
            bookmarks=bookmarks,
            device_id=device_id,
            db=db,
        )

    # Sync reading progress from Content table
    if content_rows:
        result["content"] = await _sync_content_progress(
            user_id=sync_token.user_id,
            content_rows=content_rows,
            db=db,
        )

    return result


async def _sync_content_progress(
    user_id: int,
    content_rows: list[dict],
    db: AsyncSession,
) -> dict:
    """Sync reading progress from Kobo Content table rows.

    Smart merge: only update if TimeSpentReading is higher (prevents
    data loss when a book is removed from the device and Kobo zeros data).
    """
    from app.services.kobo_annotations import resolve_volume_id
    from app.models.progress import KoboBookState

    updated = 0
    skipped = 0

    for row in content_rows:
        content_id = row.get("ContentID") or row.get("content_id", "")
        if not content_id:
            skipped += 1
            continue

        pct = row.get("___PercentRead") or row.get("percent_read", 0)
        time_spent = row.get("TimeSpentReading") or row.get("time_spent_reading", 0)

        edition_id = await resolve_volume_id(content_id, db)
        if not edition_id:
            skipped += 1
            continue

        # Find or create KoboBookState
        state_result = await db.execute(
            select(KoboBookState).where(
                KoboBookState.user_id == user_id,
                KoboBookState.edition_id == edition_id,
            )
        )
        state = state_result.scalar_one_or_none()

        if state:
            # Smart merge: only update if device has more reading time
            if time_spent > state.time_spent_reading:
                state.time_spent_reading = time_spent
                state.content_source_progress = float(pct) / 100 if pct > 1 else float(pct)
                updated += 1
            else:
                skipped += 1
        else:
            state = KoboBookState(
                user_id=user_id,
                edition_id=edition_id,
                time_spent_reading=time_spent,
                content_source_progress=float(pct) / 100 if pct > 1 else float(pct),
                status="Reading" if pct < 100 else "Finished",
            )
            db.add(state)
            updated += 1

    await db.commit()
    return {"updated": updated, "skipped": skipped}


# ---------------------------------------------------------------------------
# library_items — bare /library/{uuid} endpoint
# ---------------------------------------------------------------------------
# The initialization Resources tell the device to call
#   library_items = .../v1/library/{ItemId}
# for individual book details. Without this, the request falls through to
# the catch-all and gets {}, causing Nickel to store the book with no
# DownloadUrl. This endpoint returns the full entitlement so Nickel can
# extract the DownloadUrl and initiate the download.

@kobo_device_router.get("/kobo/{auth_token}/v1/library/{book_uuid}")
async def kobo_library_item(
    auth_token: str,
    book_uuid: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Return full entitlement for a single book.

    Called by Nickel via the library_items Resource URL. Must include
    DownloadUrls so the device can initiate wireless downloads.
    """
    sync_token = await _get_sync_token(auth_token, db)

    from sqlalchemy.orm import selectinload
    from app.models import Book, Work
    from app.services.kobo_sync import (
        _build_edition_entry,
        _get_kobo_compatible_file_edition,
    )

    base = select(Book).options(
        selectinload(Book.work).selectinload(Work.authors),
        selectinload(Book.work).selectinload(Work.series),
        selectinload(Book.files),
    )
    stmt = base.where(Book.uuid == book_uuid)
    result = await db.execute(stmt)
    book = result.scalar_one_or_none()
    if book is None and book_uuid.isdigit():
        stmt = base.where(Book.id == int(book_uuid))
        result = await db.execute(stmt)
        book = result.scalar_one_or_none()

    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    epub_file = _get_kobo_compatible_file_edition(book.files)
    if not epub_file:
        raise HTTPException(status_code=404, detail="No compatible file")

    base_url = _get_base_url(request)
    entry = _build_edition_entry(
        edition=book,
        edition_file=epub_file,
        state=None,
        auth_token=sync_token.token,
        base_url=base_url,
        is_new=False,
    )

    # Return the full entitlement envelope
    return JSONResponse(
        content=entry,
        media_type="application/json; charset=utf-8",
    )


# ---------------------------------------------------------------------------
# Catch-all for unhandled Kobo endpoints
# ---------------------------------------------------------------------------

@kobo_device_router.api_route(
    "/kobo/{auth_token}/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE"],
)
async def kobo_catch_all(
    auth_token: str,
    path: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Catch-all for Kobo endpoints we don't implement yet.

    Returns appropriate empty responses based on the path pattern.
    Specific no-ops for analytics, nextread, etc. to prevent device errors.
    """
    await _get_sync_token(auth_token, db)
    logger.debug("Unhandled Kobo endpoint: %s %s", request.method, path)

    # Analytics events — device sends these frequently, just acknowledge
    if "analytics" in path:
        return Response(status_code=200, content="{}", media_type="application/json")

    # Nextread recommendations — return empty
    if "nextread" in path:
        return JSONResponse(content={"NewEntitlement": None, "SyncToken": None})

    # Download keys — return empty success
    if "downloadkeys" in path:
        return Response(status_code=200, content="[]", media_type="application/json")

    # Default: return 200 with empty JSON object (not array — some endpoints expect object)
    return Response(
        status_code=200,
        content="{}",
        media_type="application/json",
        headers={"x-kobo-apitoken": "e30="},
    )


# ---------------------------------------------------------------------------
# Management router (JWT-authed, under /api/v1)
# ---------------------------------------------------------------------------
from app.api.auth import get_current_user
from app.models.progress import KoboTokenShelf
from app.models.shelf import Shelf
from sqlalchemy import select as sa_select

kobo_management_router = APIRouter(prefix="/kobo", tags=["kobo"])


class SyncTokenCreate(BaseModel):
    """Request to generate a new Kobo sync token."""
    device_name: Optional[str] = "Kobo eReader"
    shelf_ids: list[int] = []


class SyncTokenShelfRead(BaseModel):
    id: int
    name: str


class SyncTokenRead(BaseModel):
    """Sync token response."""
    id: int
    token: str
    sync_url: str
    is_active: bool
    created_at: str
    last_used: Optional[str] = None
    shelves: list[SyncTokenShelfRead] = []

    class Config:
        from_attributes = True


async def _token_to_response(token: KoboSyncToken, base_url: str, db: AsyncSession) -> dict:
    """Convert a KoboSyncToken to a SyncTokenRead-compatible dict."""
    # Load attached shelves
    shelf_rows = await db.execute(
        sa_select(KoboTokenShelf.shelf_id).where(KoboTokenShelf.token_id == token.id)
    )
    shelf_ids = [r[0] for r in shelf_rows]
    shelves = []
    if shelf_ids:
        result = await db.execute(
            sa_select(Shelf.id, Shelf.name).where(Shelf.id.in_(shelf_ids))
        )
        shelves = [{"id": r[0], "name": r[1]} for r in result]

    return {
        "id": token.id,
        "token": token.token,
        "sync_url": build_sync_url(token.token, base_url),
        "is_active": token.is_active,
        "created_at": token.created_at.isoformat() if token.created_at else "",
        "last_used": token.last_used.isoformat() if token.last_used else None,
        "shelves": shelves,
    }


@kobo_management_router.post("/tokens", response_model=SyncTokenRead)
async def create_kobo_token(
    body: SyncTokenCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate a new Kobo sync token.

    Returns the token and the full sync URL to configure on the Kobo device.
    Optionally accepts shelf_ids to restrict sync to books on those shelves.
    """
    sync_token = await generate_sync_token(
        user_id=current_user.id,
        db=db,
        shelf_ids=body.shelf_ids or None,
    )
    base_url = _get_base_url(request)
    return await _token_to_response(sync_token, base_url, db)


@kobo_management_router.get("/tokens", response_model=list[SyncTokenRead])
async def list_kobo_tokens(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all Kobo sync tokens for the current user."""
    tokens = await list_user_sync_tokens(current_user.id, db)
    base_url = _get_base_url(request)
    return [await _token_to_response(t, base_url, db) for t in tokens]


@kobo_management_router.put("/tokens/{token_id}/shelves")
async def set_token_shelves(
    token_id: int,
    shelf_ids: list[int],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Replace the shelf filter on an existing token."""
    # Verify token belongs to user
    result = await db.execute(
        sa_select(KoboSyncToken).where(
            KoboSyncToken.id == token_id,
            KoboSyncToken.user_id == current_user.id,
        )
    )
    token = result.scalar_one_or_none()
    if not token:
        raise HTTPException(status_code=404, detail="Token not found")

    # Replace all shelf associations
    await db.execute(
        sa_select(KoboTokenShelf).where(KoboTokenShelf.token_id == token_id)
    )
    existing = await db.execute(
        sa_select(KoboTokenShelf).where(KoboTokenShelf.token_id == token_id)
    )
    for row in existing.scalars().all():
        await db.delete(row)
    for sid in shelf_ids:
        db.add(KoboTokenShelf(token_id=token_id, shelf_id=sid))
    await db.commit()
    return {"status": "ok", "shelf_ids": shelf_ids}


@kobo_management_router.delete("/tokens/{token_id}")
async def delete_kobo_token(
    token_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Revoke a Kobo sync token."""
    success = await revoke_sync_token(token_id, db)
    if not success:
        raise HTTPException(status_code=404, detail="Token not found")
    return {"status": "revoked"}
