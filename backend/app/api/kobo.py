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
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
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
    """Extract the base URL from the incoming request for building absolute URLs."""
    scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.url.netloc)
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

    response = JSONResponse(content=items)

    if has_more:
        response.headers["X-Kobo-Sync"] = "continue"

    return response


@kobo_device_router.get("/kobo/{auth_token}/v1/library/{book_uuid}/metadata")
async def kobo_book_metadata(
    auth_token: str,
    book_uuid: str,
    db: AsyncSession = Depends(get_db),
):
    """Get metadata for a specific book.

    The device may call this for individual book details after the sync
    endpoint provides the overview.
    """
    sync_token = await _get_sync_token(auth_token, db)

    # For now, return a minimal metadata response
    # The full sync already provides complete metadata
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models import Book

    stmt = (
        select(Book)
        .where(Book.uuid == book_uuid)
        .options(selectinload(Book.authors), selectinload(Book.files))
    )
    result = await db.execute(stmt)
    book = result.scalar_one_or_none()

    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    author_name = ", ".join(a.name for a in book.authors) if book.authors else ""

    return {
        "Title": book.title,
        "Contributors": author_name,
        "Description": book.description or "",
        "Language": book.language or "en",
        "EntitlementId": book.uuid,
        "CrossRevisionId": book.uuid,
        "RevisionId": book.uuid,
        "WorkId": book.uuid,
    }


@kobo_device_router.get("/kobo/{auth_token}/v1/library/{book_uuid}/state")
async def kobo_get_reading_state(
    auth_token: str,
    book_uuid: str,
    db: AsyncSession = Depends(get_db),
):
    """Get the reading state for a specific book."""
    sync_token = await _get_sync_token(auth_token, db)

    from sqlalchemy import select
    from app.models import Book
    from app.models.progress import KoboBookState
    from app.services.kobo_sync import _build_reading_state

    stmt = select(Book).where(Book.uuid == book_uuid)
    result = await db.execute(stmt)
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    state_stmt = select(KoboBookState).where(
        KoboBookState.user_id == sync_token.user_id,
        KoboBookState.book_id == book.id,
    )
    state_result = await db.execute(state_stmt)
    state = state_result.scalar_one_or_none()

    if not state:
        # Return default state
        return {
            "ReadingState": {
                "EntitlementId": book_uuid,
                "StatusInfo": {"Status": "ReadyToRead", "TimesStartedReading": 0},
                "Statistics": {},
                "CurrentBookmark": {"ProgressPercent": 0},
            }
        }

    return {"ReadingState": _build_reading_state(book_uuid, state)}


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

    # Device sends { "ReadingStates": [ {...} ] } — take the first element
    reading_states = body.get("ReadingStates", [])
    state_data = reading_states[0] if reading_states else body

    state = await update_reading_state(
        book_uuid=book_uuid,
        user_id=sync_token.user_id,
        state_data=state_data,
        db=db,
    )

    if not state:
        raise HTTPException(status_code=404, detail="Book not found")

    return {
        "RequestResult": "Success",
        "UpdateResults": [
            {
                "EntitlementId": book_uuid,
                "CurrentBookmarkResult": {"Result": "Success"},
                "StatisticsResult": {"Result": "Ignored"},
                "StatusInfoResult": {"Result": "Success"},
            }
        ],
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
        "kepub": "application/epub+zip",
        "pdf": "application/pdf",
    }
    media_type = media_types.get(file_format.lower(), "application/octet-stream")

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=file_path.name,
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
    from app.models import Shelf

    stmt = (
        select(Shelf)
        .where(Shelf.user_id == sync_token.user_id)
        .options(selectinload(Shelf.books))
    )
    result = await db.execute(stmt)
    shelves = result.scalars().all()

    tags = []
    for shelf in shelves:
        created = shelf.created_at.strftime("%Y-%m-%dT%H:%M:%SZ") if shelf.created_at else None
        items = [
            {"RevisionId": book.uuid, "Type": "ProductRevisionTagItem"}
            for book in shelf.books
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
# Catch-all for unhandled Kobo endpoints
# ---------------------------------------------------------------------------

@kobo_device_router.api_route(
    "/kobo/{auth_token}/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE"],
)
async def kobo_catch_all(
    auth_token: str,
    path: str,
    db: AsyncSession = Depends(get_db),
):
    """Catch-all for Kobo endpoints we don't implement yet.

    Returns empty success responses to prevent the device from erroring out.
    Logs the path for future implementation.
    """
    await _get_sync_token(auth_token, db)
    logger.debug(f"Unhandled Kobo endpoint: /kobo/.../{ path}")
    return Response(status_code=200, content="[]", media_type="application/json")


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
