"""AudiobookShelf integration endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.config import get_settings
from app.models.user import User

from .auth import get_current_user

router = APIRouter(prefix="/audiobookshelf")


class ImportRequest(BaseModel):
    abs_library_id: str
    scriptorium_library_id: int
    limit: int = 0  # 0 = all


class LinkRequest(BaseModel):
    book_id: int
    abs_item_id: str


@router.get("/status")
async def abs_status(current_user: User = Depends(get_current_user)):
    """Return ABS connection status and server info."""
    s = get_settings()
    if not s.ABS_URL or not s.ABS_API_KEY:
        return {"configured": False, "connected": False}

    from app.services.audiobookshelf import AudiobookShelfClient
    client = AudiobookShelfClient(s.ABS_URL, s.ABS_API_KEY)
    try:
        info = await client.get_server_info()
        user_info = info.get("user", {})
        return {
            "configured": True,
            "connected": True,
            "server_url": s.ABS_URL,
            "abs_user": user_info.get("username"),
            "abs_user_type": user_info.get("type"),
        }
    except Exception as exc:
        return {"configured": True, "connected": False, "error": str(exc)}


@router.get("/libraries")
async def abs_libraries(current_user: User = Depends(get_current_user)):
    """List libraries from the ABS instance."""
    s = get_settings()
    if not s.ABS_URL or not s.ABS_API_KEY:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="AudiobookShelf not configured")

    from app.services.audiobookshelf import AudiobookShelfClient
    client = AudiobookShelfClient(s.ABS_URL, s.ABS_API_KEY)
    try:
        libraries = await client.get_libraries()
        return [
            {
                "id": lib.get("id"),
                "name": lib.get("name"),
                "media_type": lib.get("mediaType"),
                "icon": lib.get("icon"),
            }
            for lib in libraries
        ]
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))


@router.post("/sync-progress")
async def abs_sync_progress(current_user: User = Depends(get_current_user)):
    """Pull listening progress from ABS → Scriptorium ReadProgress for the current user."""
    s = get_settings()
    if not s.ABS_URL or not s.ABS_API_KEY:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="AudiobookShelf not configured")

    from app.services.audiobookshelf import sync_progress
    result = await sync_progress(current_user.id)
    if "error" in result:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=result["error"])
    return result


@router.post("/import")
async def abs_import(
    req: ImportRequest,
    current_user: User = Depends(get_current_user),
):
    """Import items from an ABS library into a Scriptorium library."""
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")

    s = get_settings()
    if not s.ABS_URL or not s.ABS_API_KEY:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="AudiobookShelf not configured")

    from app.services.audiobookshelf import import_library_items
    result = await import_library_items(
        req.abs_library_id,
        req.scriptorium_library_id,
        current_user.id,
        req.limit,
    )
    if "error" in result:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=result["error"])
    return result


@router.post("/sync-covers")
async def abs_sync_covers(
    overwrite: bool = False,
    current_user: User = Depends(get_current_user),
):
    """Fetch covers from ABS for linked books missing a cover (or all if overwrite=True). Admin only."""
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")

    s = get_settings()
    if not s.ABS_URL or not s.ABS_API_KEY:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="AudiobookShelf not configured")

    from app.services.audiobookshelf import sync_covers
    result = await sync_covers(overwrite=overwrite)
    if "error" in result:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=result["error"])
    return result


@router.post("/link")
async def abs_link_book(
    req: LinkRequest,
    current_user: User = Depends(get_current_user),
):
    """Manually link a Scriptorium book to an ABS item ID."""
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")

    from sqlalchemy import select
    from app.database import get_db
    from fastapi import Request
    from app.models.book import Book

    # Use get_db via dependency manually
    from app.database import get_session_factory
    factory = get_session_factory()
    async with factory() as db:
        result = await db.execute(select(Book).where(Book.id == req.book_id))
        book = result.scalar_one_or_none()
        if not book:
            raise HTTPException(status_code=404, detail="Book not found")
        book.abs_item_id = req.abs_item_id
        await db.commit()
    return {"book_id": req.book_id, "abs_item_id": req.abs_item_id}


@router.delete("/link/{book_id}")
async def abs_unlink_book(
    book_id: int,
    current_user: User = Depends(get_current_user),
):
    """Remove the ABS link from a Scriptorium book."""
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")

    from sqlalchemy import select
    from app.database import get_session_factory
    from app.models.book import Book

    factory = get_session_factory()
    async with factory() as db:
        result = await db.execute(select(Book).where(Book.id == book_id))
        book = result.scalar_one_or_none()
        if not book:
            raise HTTPException(status_code=404, detail="Book not found")
        book.abs_item_id = None
        await db.commit()
    return {"book_id": book_id, "abs_item_id": None}
