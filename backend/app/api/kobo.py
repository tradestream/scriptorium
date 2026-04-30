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
from pathlib import Path
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
    revoke_sync_token_for_user,
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


async def _resolve_book_for_token(
    book_uuid: str,
    sync_token: KoboSyncToken,
    db: AsyncSession,
):
    """Resolve a book by UUID (or numeric id) and enforce per-token library access.

    Returns the Book/Edition row or raises 404. Returning 404 (not 403) avoids
    leaking the existence of books in libraries the token's user can't see.
    """
    from sqlalchemy.orm import selectinload

    from app.api.auth import get_accessible_library_ids
    from app.models import Book, Work
    from app.models.user import User as _User

    user = await db.get(_User, sync_token.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    accessible_lib_ids = await get_accessible_library_ids(db, user)

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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")

    if accessible_lib_ids is not None and book.library_id not in accessible_lib_ids:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")

    return book


def _get_base_url(request: Request) -> str:
    """Extract the base URL from the incoming request for building absolute URLs.

    Resolution lives in ``app.utils.request_url.public_base_url`` (prefers
    ``PUBLIC_BASE_URL``; honours ``X-Forwarded-*`` only when
    ``TRUST_FORWARDED_HEADERS`` is on; otherwise the request's own
    scheme + host). After that, force HTTPS for non-local hosts since
    Kobo devices reject plain HTTP downloads.
    """
    from app.utils.request_url import public_base_url

    base = public_base_url(request)
    scheme, _, host = base.partition("://")
    if scheme == "http" and host and not any(
        h in host for h in ("localhost", "127.0.0.1", "192.168.", "10.", "172.")
    ):
        return f"https://{host}"
    return base


# ---------------------------------------------------------------------------
# Cover images — served at the image_url_quality_template path
# ---------------------------------------------------------------------------
# The initialization tells the device to fetch covers at:
#   /covers/{ImageId}/{Width}/{Height}/{grayscale}/image.jpg
# ImageId is "{uuid}-{cover_hash}" (for cache busting). We strip the
# hash suffix, look up the cover file by UUID, and serve it.
# WITHOUT this endpoint, every cover request 404s and Nickel may roll
# back the entire entitlement, preventing books from appearing.

@kobo_device_router.get("/covers/{image_id}/{width}/{height}/{grayscale}/image.jpg")
@kobo_device_router.get("/covers/{image_id}/image.jpg")
async def kobo_cover_image(
    image_id: str,
    width: int = 0,
    height: int = 0,
    grayscale: str = "false",
    db: AsyncSession = Depends(get_db),
):
    """Serve a book cover image to the Kobo device."""
    from app.config import get_settings
    from app.models import Edition
    settings = get_settings()

    # Strip the -hash suffix to get the UUID
    uuid = image_id.split("-", 5)
    if len(uuid) >= 5:
        # UUID is first 5 dash-separated segments: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
        edition_uuid = "-".join(uuid[:5])
    else:
        edition_uuid = image_id

    stmt = select(Edition).where(Edition.uuid == edition_uuid)
    result = await db.execute(stmt)
    edition = result.scalar_one_or_none()

    if not edition or not edition.cover_format:
        raise HTTPException(status_code=404, detail="No cover")
    # cover_hash is only used for cache-busting in the CoverImageId URL;
    # it's not required to serve the actual cover file.

    cover_path = Path(settings.COVERS_PATH) / f"{edition.uuid}.{edition.cover_format}"
    if not cover_path.exists():
        raise HTTPException(status_code=404, detail="Cover file not found")

    media_type = "image/jpeg" if edition.cover_format in ("jpg", "jpeg") else f"image/{edition.cover_format}"
    return FileResponse(str(cover_path), media_type=media_type)


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
    # CWA cps/kobo.py L430-431: only set x-kobo-sync when there are more
    # pages ("continue"). When sync is complete (no more pages), OMIT the
    # header entirely. Setting it to "" (empty string) triggers Nickel's
    # reconciliation logic which interprets an empty sync response as
    # "your library is empty" and DELETES all previously-synced entitlements.
    # Omitting the header means "no changes" — Nickel preserves existing books.
    if has_more:
        response.headers["x-kobo-sync"] = "continue"
    response.headers["x-kobo-synctoken"] = sync_token_b64
    response.headers["x-kobo-apitoken"] = "e30="
    # Nickel's LibraryParser::parseHeaders reads these two headers.
    # Missing headers may cause the parser to skip processing entitlements.
    response.headers["x-kobo-recent-reads"] = ""
    response.headers["x-kobo-sync-mode"] = ""

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

    from app.services.kobo_sync import (
        _build_edition_entry,
        _get_kobo_compatible_file_edition,
    )

    book = await _resolve_book_for_token(book_uuid, sync_token, db)

    epub_file = _get_kobo_compatible_file_edition(book.files)
    if not epub_file:
        raise HTTPException(status_code=404, detail="No compatible file")

    base_url = _get_base_url(request)
    # Pull live progress so the metadata response carries the same
    # ReadingState/Bookmark the device would see via the sync feed.
    from app.models.reading import EditionPosition as _EP
    from app.models.reading import ReadingState as _RS
    ep = (
        await db.execute(
            select(_EP).where(_EP.user_id == sync_token.user_id, _EP.edition_id == book.id)
        )
    ).scalar_one_or_none()
    rs = None
    if book.work_id is not None:
        rs = (
            await db.execute(
                select(_RS).where(_RS.user_id == sync_token.user_id, _RS.work_id == book.work_id)
            )
        ).scalar_one_or_none()

    entry = _build_edition_entry(
        edition=book,
        edition_file=epub_file,
        ep=ep,
        rs=rs,
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

    from app.models.reading import EditionPosition, ReadingState
    from app.services.kobo_sync import (
        _build_reading_state,
        _find_edition_by_any_id,
        _resolve_emit_span,
    )

    book = await _find_edition_by_any_id(book_uuid, db)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    ep = (
        await db.execute(
            select(EditionPosition).where(
                EditionPosition.user_id == sync_token.user_id,
                EditionPosition.edition_id == book.id,
            )
        )
    ).scalar_one_or_none()
    rs = None
    if book.work_id is not None:
        rs = (
            await db.execute(
                select(ReadingState).where(
                    ReadingState.user_id == sync_token.user_id,
                    ReadingState.work_id == book.work_id,
                )
            )
        ).scalar_one_or_none()

    if ep is None and rs is None:
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

    # Resolve a real KoboSpan id when our cursor format permits. Pull
    # the EditionFile rows directly (book.files lazy-load can MissingGreenlet
    # in this async path).
    from app.models.edition import EditionFile
    files = list(
        (
            await db.execute(
                select(EditionFile).where(EditionFile.edition_id == book.id)
            )
        ).scalars().all()
    )
    span_chapter, span_id = await _resolve_emit_span(ep, files, db)

    return [
        _build_reading_state(
            book_uuid,
            ep=ep,
            rs=rs,
            span_chapter_href=span_chapter,
            span_id=span_id,
        )
    ]


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


@kobo_device_router.delete("/kobo/{auth_token}/v1/library/{book_uuid}")
async def kobo_delete_book(
    auth_token: str,
    book_uuid: str,
    db: AsyncSession = Depends(get_db),
):
    """Device-side archive — the Kobo deleted this book locally.

    Critical: this does **not** delete the file, the edition, the work,
    or the library row. It only marks the (token, edition) pair as
    archived in ``kobo_synced_books`` so the next sync pass won't push
    it back to the device. The user has to re-add via Scriptorium to
    un-archive.

    Equivalent to CWA's ``DELETE /v1/library/{book_uuid}``.
    """
    sync_token = await _get_sync_token(auth_token, db)
    edition = await _resolve_book_for_token(book_uuid, sync_token, db)
    if edition is None:
        # No-op: device asked to remove something we never sent or
        # don't recognize. 204 keeps the device happy either way.
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    from datetime import datetime as _dt

    from sqlalchemy import update as _update

    from app.models.progress import KoboSyncedBook

    # Stamp archived_at on the existing synced row, if any. We don't
    # create a row when none exists — there's nothing to "un-sync."
    await db.execute(
        _update(KoboSyncedBook)
        .where(
            KoboSyncedBook.sync_token_id == sync_token.id,
            KoboSyncedBook.edition_id == edition.id,
            KoboSyncedBook.archived_at.is_(None),
        )
        .values(archived_at=_dt.utcnow())
    )
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@kobo_device_router.get(
    "/kobo/{auth_token}/v1/library/{book_uuid}/download/{file_format}"
)
async def kobo_download_book(
    auth_token: str,
    book_uuid: str,
    file_format: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Download a book file to the Kobo device.

    Serves the actual EPUB/KEPUB/PDF file for sideloading onto the device.
    """
    sync_token = await _get_sync_token(auth_token, db)

    file_path = await get_download_path(book_uuid, file_format, db, sync_token=sync_token)
    if not file_path:
        raise HTTPException(status_code=404, detail="Book file not found")

    media_types = {
        "epub": "application/epub+zip",
        "kepub": "application/kepub+zip",
        "pdf": "application/pdf",
    }
    media_type = media_types.get(file_format.lower(), "application/octet-stream")

    # Kobo resumes downloads via Range + ETag/Last-Modified; the shared
    # streaming helper handles all of that plus If-Range fallback. We salt
    # the ETag with the book UUID so the same on-disk path served as
    # different entitlements doesn't collide in the device cache.
    from app.services.file_streaming import stream_file_response
    return stream_file_response(
        request,
        file_path,
        media_type=media_type,
        filename=file_path.name,
        etag_salt=book_uuid,
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

    from app.models.collection import Collection
    from app.models.progress import KoboShelfArchive
    from app.models.shelf import Shelf

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

    from sqlalchemy import select

    from app.models.progress import KoboShelfArchive

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

    from app.models.collection import Collection, CollectionBook
    from app.models.progress import KoboShelfArchive
    from app.models.shelf import ShelfBook

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


async def _remove_item_from_tag(
    archive,
    item_id: str,
    user_id: int,
    db: AsyncSession,
) -> None:
    """Drop a single book from a Kobo-mirrored tag (shelf + collection).

    Shared by both the per-item DELETE route and the bulk-delete POST.
    Silently no-ops if the edition can't be resolved (the device may
    pass a stale UUID after a metadata refresh; better to swallow than
    refuse the whole batch).
    """
    from app.models.collection import Collection, CollectionBook
    from app.models.shelf import ShelfBook
    from app.services.kobo_sync import _find_edition_by_any_id

    edition = await _find_edition_by_any_id(item_id, db)
    if edition is None:
        return
    if archive.shelf_id:
        sb = (
            await db.execute(
                select(ShelfBook).where(
                    ShelfBook.shelf_id == archive.shelf_id,
                    ShelfBook.work_id == edition.work_id,
                )
            )
        ).scalar_one_or_none()
        if sb:
            await db.delete(sb)

    col = (
        await db.execute(
            select(Collection).where(
                Collection.user_id == user_id, Collection.name == archive.name
            )
        )
    ).scalar_one_or_none()
    if col:
        cb = (
            await db.execute(
                select(CollectionBook).where(
                    CollectionBook.collection_id == col.id,
                    CollectionBook.work_id == edition.work_id,
                )
            )
        ).scalar_one_or_none()
        if cb:
            await db.delete(cb)


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

    archive = (
        await db.execute(
            select(KoboShelfArchive).where(
                KoboShelfArchive.user_id == sync_token.user_id,
                KoboShelfArchive.kobo_tag_id == tag_id,
            )
        )
    ).scalar_one_or_none()
    if not archive:
        return Response(status_code=404)

    await _remove_item_from_tag(archive, item_id, sync_token.user_id, db)
    await db.commit()
    return Response(status_code=204)


@kobo_device_router.post("/kobo/{auth_token}/v1/library/tags/{tag_id}/items/delete")
async def kobo_bulk_remove_items_from_tag(
    auth_token: str,
    tag_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Bulk-remove multiple books from a tag in one device round-trip.

    Body shape (CWA / Kobo wire format):
      {"Items": [{"RevisionId": "uuid-1"}, {"RevisionId": "uuid-2"}, ...]}

    Each item is processed via the same per-item logic as the DELETE
    route. Missing / unresolvable UUIDs are skipped silently rather
    than failing the whole batch — the device's view of which books
    belong to a tag can drift, and a hard error would leave the user's
    "remove from collection" UX broken.
    """
    sync_token = await _get_sync_token(auth_token, db)

    from app.models.progress import KoboShelfArchive

    archive = (
        await db.execute(
            select(KoboShelfArchive).where(
                KoboShelfArchive.user_id == sync_token.user_id,
                KoboShelfArchive.kobo_tag_id == tag_id,
            )
        )
    ).scalar_one_or_none()
    if not archive:
        return Response(status_code=404)

    try:
        body = await request.json()
    except Exception:
        body = {}
    items = body.get("Items") or body.get("items") or []
    if not isinstance(items, list):
        items = []

    for entry in items:
        if not isinstance(entry, dict):
            continue
        # Kobo uses ``RevisionId`` for the book uuid; some firmware
        # variants also send ``Id``.
        item_id = entry.get("RevisionId") or entry.get("Id")
        if item_id:
            await _remove_item_from_tag(archive, str(item_id), sync_token.user_id, db)

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
    data loss when a book is removed from the device and Kobo zeros
    data). Writes go through the unified write_progress helper —
    EditionPosition cumulative time_spent_seconds takes the role
    KoboBookState.time_spent_reading used to play.
    """
    from app.models.edition import Edition
    from app.models.reading import EditionPosition
    from app.services.kobo_annotations import resolve_volume_id
    from app.services.kobo_sync import _get_or_create_kobo_device
    from app.services.unified_progress import write_progress

    updated = 0
    skipped = 0
    device = await _get_or_create_kobo_device(user_id, db)

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

        edition = await db.get(Edition, edition_id)
        if edition is None:
            skipped += 1
            continue

        # Smart merge: skip when this device hasn't read any longer than
        # the cumulative recorded time. Avoids regressing time totals when
        # the device wipes per-title stats.
        ep = (
            await db.execute(
                select(EditionPosition).where(
                    EditionPosition.user_id == user_id,
                    EditionPosition.edition_id == edition_id,
                )
            )
        ).scalar_one_or_none()
        prior_seconds = ep.time_spent_seconds if ep else 0
        incoming_seconds = int(time_spent or 0)
        delta = max(0, incoming_seconds - prior_seconds)
        if ep is not None and delta == 0 and (not pct or pct == 0):
            skipped += 1
            continue

        # Normalize percent: device reports either 0–1 fractions or 0–100
        # depending on column origin.
        cursor_pct = (
            float(pct) if (pct is not None and pct <= 1) else float(pct or 0) / 100.0
        )

        await write_progress(
            db,
            user_id=user_id,
            edition=edition,
            cursor_format="percent",
            cursor_value=str(round(cursor_pct * 100, 4)),
            cursor_pct=cursor_pct,
            device_id=device.id,
            time_spent_delta_seconds=delta,
            status_hint="completed" if cursor_pct >= 0.97 else None,
        )
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

    from app.services.kobo_sync import (
        _build_edition_entry,
        _get_kobo_compatible_file_edition,
    )

    book = await _resolve_book_for_token(book_uuid, sync_token, db)

    epub_file = _get_kobo_compatible_file_edition(book.files)
    if not epub_file:
        raise HTTPException(status_code=404, detail="No compatible file")

    base_url = _get_base_url(request)
    from app.models.reading import EditionPosition as _EP
    from app.models.reading import ReadingState as _RS
    ep = (
        await db.execute(
            select(_EP).where(_EP.user_id == sync_token.user_id, _EP.edition_id == book.id)
        )
    ).scalar_one_or_none()
    rs = None
    if book.work_id is not None:
        rs = (
            await db.execute(
                select(_RS).where(_RS.user_id == sync_token.user_id, _RS.work_id == book.work_id)
            )
        ).scalar_one_or_none()

    entry = _build_edition_entry(
        edition=book,
        edition_file=epub_file,
        ep=ep,
        rs=rs,
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
from sqlalchemy import select as sa_select

from app.api.auth import get_current_user
from app.models.progress import KoboTokenShelf
from app.models.shelf import Shelf

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
    """Replace the shelf filter on an existing token.

    Only shelves owned by the requesting user are accepted. Shelf ids the user
    does not own are silently dropped — they would otherwise let one user
    mirror another user's shelf onto their own Kobo.
    """
    from app.models.shelf import Shelf

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

    # Filter to shelves the requester actually owns.
    if shelf_ids:
        owned_rows = await db.execute(
            sa_select(Shelf.id).where(
                Shelf.id.in_(shelf_ids), Shelf.user_id == current_user.id
            )
        )
        owned_ids = [row[0] for row in owned_rows.all()]
    else:
        owned_ids = []

    # Replace all shelf associations
    existing = await db.execute(
        sa_select(KoboTokenShelf).where(KoboTokenShelf.token_id == token_id)
    )
    for row in existing.scalars().all():
        await db.delete(row)
    for sid in owned_ids:
        db.add(KoboTokenShelf(token_id=token_id, shelf_id=sid))
    await db.commit()
    return {"status": "ok", "shelf_ids": owned_ids}


@kobo_management_router.delete("/tokens/{token_id}")
async def delete_kobo_token(
    token_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Revoke a Kobo sync token."""
    success = await revoke_sync_token_for_user(token_id, current_user.id, db)
    if not success:
        raise HTTPException(status_code=404, detail="Token not found")
    return {"status": "revoked"}
