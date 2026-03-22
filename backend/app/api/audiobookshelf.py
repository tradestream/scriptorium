"""AudiobookShelf integration endpoints."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel

from app.config import get_settings
from app.models.user import User
from app.services.background_jobs import create_job, get_job, update_job, get_job_status

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
    background_tasks: BackgroundTasks = None,
    current_user: User = Depends(get_current_user),
):
    """Fetch covers from ABS for linked books missing a cover (or all if overwrite=True).

    Runs as a background task and returns a job_id for polling. Admin only.
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")

    s = get_settings()
    if not s.ABS_URL or not s.ABS_API_KEY:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="AudiobookShelf not configured")

    # Count how many editions will be processed
    from sqlalchemy import select, func
    from app.database import get_session_factory
    from app.models.edition import Edition

    factory = get_session_factory()
    async with factory() as db:
        eq = select(func.count(Edition.id)).where(Edition.abs_item_id.isnot(None))
        if not overwrite:
            eq = eq.where(Edition.cover_hash.is_(None))
        total = (await db.execute(eq)).scalar() or 0

    job_id, _ = await create_job("cover_sync", total)
    background_tasks.add_task(_run_cover_sync, job_id, overwrite)
    return {"job_id": job_id, "total": total}


@router.get("/sync-covers/{job_id}")
async def get_cover_sync_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
):
    """Poll the status of a cover-sync job."""
    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": job_id, **job}


async def _run_cover_sync(job_id: str, overwrite: bool) -> None:
    """Background task: fetch ABS covers one by one, updating job state."""
    from sqlalchemy import select
    from app.database import get_session_factory
    from app.models.edition import Edition
    from app.services.audiobookshelf import _get_client, _fetch_abs_cover
    from app.services import covers as cover_service

    await update_job(job_id, status="running")

    client = _get_client()
    if not client:
        await update_job(job_id, status="failed")
        return

    done = 0
    failed = 0

    factory = get_session_factory()
    async with factory() as db:
        eq = select(Edition).where(Edition.abs_item_id.isnot(None))
        if not overwrite:
            eq = eq.where(Edition.cover_hash.is_(None))
        editions = (await db.execute(eq)).scalars().all()

        for edition in editions:
            if await get_job_status(job_id) == "cancelled":
                break
            cover_bytes = await _fetch_abs_cover(client, edition.abs_item_id)
            if not cover_bytes:
                failed += 1
                done += 1
                await update_job(job_id, done=done, failed=failed)
                continue
            h, fmt, *_ = await cover_service.save_cover(cover_bytes, edition.uuid)
            if h:
                edition.cover_hash = h
                edition.cover_format = fmt
            else:
                failed += 1
            done += 1
            await update_job(job_id, done=done, failed=failed)

        await db.commit()

    final_status = await get_job_status(job_id)
    if final_status == "running":
        await update_job(job_id, status="completed")
    # else keep cancelled/failed status


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
