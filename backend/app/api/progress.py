"""Reading progress and statistics API."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.database import get_db
from app.models import Book, ReadProgress
from app.models.library import Library
from app.models.progress import Device, KoboBookState
from app.models.work import Work
from app.models.read_session import ReadSession
from app.models.user import User

from .auth import get_current_user

router = APIRouter()


class ProgressUpdate(BaseModel):
    current_page: int = 0
    total_pages: Optional[int] = None
    percentage: float = 0.0
    file_id: Optional[int] = None
    format: Optional[str] = None
    status: str = "reading"  # want_to_read, reading, completed, abandoned
    rating: Optional[int] = None  # 1-5


class StatusUpdate(BaseModel):
    status: Optional[str] = None  # want_to_read, reading, completed, abandoned
    rating: Optional[int] = None  # 1-5, None to clear


async def _get_or_create_web_device(db: AsyncSession, user_id: int) -> Device:
    """Get or create a virtual 'web' device for tracking in-browser progress."""
    stmt = select(Device).where(Device.user_id == user_id, Device.device_type == "web")
    result = await db.execute(stmt)
    device = result.scalar_one_or_none()
    if not device:
        device = Device(user_id=user_id, name="Web Browser", device_type="web")
        db.add(device)
        await db.flush()
    return device


@router.get("/books/{book_id}/progress")
async def get_book_progress(
    book_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get reading progress for a specific book."""
    stmt = (
        select(ReadProgress)
        .where(ReadProgress.edition_id == book_id, ReadProgress.user_id == current_user.id)
        .order_by(ReadProgress.updated_at.desc())
    )
    result = await db.execute(stmt)
    progress = result.scalar_one_or_none()
    if not progress:
        return None
    return {
        "current_page": progress.current_page,
        "total_pages": progress.total_pages,
        "percentage": progress.percentage,
        "status": progress.status,
        "rating": progress.rating,
        "last_opened": progress.last_opened.isoformat() if progress.last_opened else None,
        "started_at": progress.started_at.isoformat() if progress.started_at else None,
        "completed_at": progress.completed_at.isoformat() if progress.completed_at else None,
    }


@router.put("/books/{book_id}/progress")
async def update_book_progress(
    book_id: int,
    data: ProgressUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upsert reading progress for a book (web reader auto-saves here)."""
    # Verify book exists
    book_result = await db.execute(select(Book).where(Book.id == book_id))
    if not book_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")

    device = await _get_or_create_web_device(db, current_user.id)

    stmt = select(ReadProgress).where(
        ReadProgress.edition_id == book_id,
        ReadProgress.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    progress = result.scalar_one_or_none()

    now = datetime.utcnow()
    if not progress:
        progress = ReadProgress(
            user_id=current_user.id,
            edition_id=book_id,
            device_id=device.id,
            started_at=now,
        )
        db.add(progress)

    progress.current_page = data.current_page
    progress.total_pages = data.total_pages
    progress.percentage = data.percentage
    progress.status = data.status
    progress.last_opened = now
    if data.rating is not None:
        progress.rating = data.rating

    if data.status == "completed" and not progress.completed_at:
        progress.completed_at = now

    await db.commit()
    return {"ok": True}


@router.patch("/books/{book_id}/progress")
async def patch_book_status(
    book_id: int,
    data: StatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Set reading status and/or rating without touching reading position."""
    book_result = await db.execute(select(Book).where(Book.id == book_id))
    if not book_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")

    device = await _get_or_create_web_device(db, current_user.id)

    stmt = select(ReadProgress).where(
        ReadProgress.edition_id == book_id,
        ReadProgress.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    progress = result.scalar_one_or_none()

    now = datetime.utcnow()
    if not progress:
        progress = ReadProgress(
            user_id=current_user.id,
            edition_id=book_id,
            device_id=device.id,
            started_at=now if data.status not in ("want_to_read", None) else None,
        )
        db.add(progress)

    if data.status is not None:
        progress.status = data.status
        if data.status == "completed" and not progress.completed_at:
            progress.completed_at = now

    if data.rating is not None:
        progress.rating = max(1, min(5, data.rating))
    elif "rating" in (data.model_fields_set or set()):
        progress.rating = None  # explicit None clears it

    await db.commit()
    return {"ok": True}


@router.get("/stats")
async def get_reading_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reading statistics for the current user."""
    uid = current_user.id

    # Status counts (exclude hidden libraries)
    async def count_status(s: str) -> int:
        r = await db.scalar(
            select(func.count(ReadProgress.id))
            .join(Book, Book.id == ReadProgress.edition_id)
            .join(Library, Library.id == Book.library_id)
            .where(
                ReadProgress.user_id == uid,
                ReadProgress.status == s,
                Library.is_hidden == False,
            )
        )
        return r or 0

    books_reading = await count_status("reading")
    books_completed = await count_status("completed")
    books_abandoned = await count_status("abandoned")

    # Pages read (exclude hidden libraries)
    pages_read = await db.scalar(
        select(func.sum(ReadProgress.current_page))
        .join(Book, Book.id == ReadProgress.edition_id)
        .join(Library, Library.id == Book.library_id)
        .where(ReadProgress.user_id == uid, Library.is_hidden == False)
    ) or 0

    # Time spent reading from Kobo (seconds)
    time_reading = await db.scalar(
        select(func.sum(KoboBookState.time_spent_reading)).where(KoboBookState.user_id == uid)
    ) or 0

    # Total books in library (exclude hidden)
    total_books = await db.scalar(
        select(func.count(Book.id))
        .join(Library, Library.id == Book.library_id)
        .where(Library.is_hidden == False)
    ) or 0

    # Currently reading (most recently opened, up to 5, exclude hidden)
    rp_stmt = (
        select(ReadProgress)
        .join(Book, Book.id == ReadProgress.edition_id)
        .join(Library, Library.id == Book.library_id)
        .where(
            ReadProgress.user_id == uid,
            ReadProgress.status == "reading",
            Library.is_hidden == False,
        )
        .order_by(ReadProgress.last_opened.desc())
        .limit(5)
    )
    rp_result = await db.execute(rp_stmt)
    reading_rows = rp_result.scalars().all()

    currently_reading = []
    for rp in reading_rows:
        book_row = await db.execute(
            select(Book).where(Book.id == rp.edition_id).options(joinedload(Book.work).options(joinedload(Work.authors)))
        )
        book = book_row.unique().scalar_one_or_none()
        if book:
            currently_reading.append(
                {
                    "id": book.id,
                    "title": book.title,
                    "author": book.authors[0].name if book.authors else None,
                    "percentage": round(rp.percentage, 1),
                    "last_opened": rp.last_opened.isoformat() if rp.last_opened else None,
                }
            )

    # Recently completed (up to 5, exclude hidden)
    rc_stmt = (
        select(ReadProgress)
        .join(Book, Book.id == ReadProgress.edition_id)
        .join(Library, Library.id == Book.library_id)
        .where(
            ReadProgress.user_id == uid,
            ReadProgress.status == "completed",
            Library.is_hidden == False,
        )
        .order_by(ReadProgress.completed_at.desc())
        .limit(5)
    )
    rc_result = await db.execute(rc_stmt)
    completed_rows = rc_result.scalars().all()

    recently_completed = []
    for rp in completed_rows:
        book_row = await db.execute(
            select(Book).where(Book.id == rp.edition_id).options(joinedload(Book.work).options(joinedload(Work.authors)))
        )
        book = book_row.unique().scalar_one_or_none()
        if book:
            recently_completed.append(
                {
                    "id": book.id,
                    "title": book.title,
                    "author": book.authors[0].name if book.authors else None,
                    "completed_at": rp.completed_at.isoformat() if rp.completed_at else None,
                }
            )

    # Sessions this year (finished reads in the current calendar year)
    year_start = datetime(datetime.utcnow().year, 1, 1)
    sessions_this_year = await db.scalar(
        select(func.count(ReadSession.id))
        .join(Book, Book.id == ReadSession.work_id)
        .join(Library, Library.id == Book.library_id)
        .where(
            ReadSession.user_id == uid,
            ReadSession.finished_at >= year_start,
            Library.is_hidden == False,
        )
    ) or 0

    # Recent sessions (reading log — last 20, exclude hidden libraries)
    rs_stmt = (
        select(ReadSession)
        .join(Book, Book.id == ReadSession.work_id)
        .join(Library, Library.id == Book.library_id)
        .where(ReadSession.user_id == uid, Library.is_hidden == False)
        .order_by(ReadSession.started_at.desc())
        .limit(20)
    )
    rs_result = await db.execute(rs_stmt)
    session_rows = rs_result.scalars().all()

    # Bulk-load books for those sessions
    session_book_ids = list({s.work_id for s in session_rows})
    books_by_id: dict[int, Book] = {}
    if session_book_ids:
        bk_result = await db.execute(
            select(Book).where(Book.id.in_(session_book_ids)).options(joinedload(Book.work).options(joinedload(Work.authors)))
        )
        for b in bk_result.unique().scalars().all():
            books_by_id[b.id] = b

    recent_sessions = []
    for s in session_rows:
        bk = books_by_id.get(s.work_id)
        if bk:
            recent_sessions.append(
                {
                    "id": s.id,
                    "book_id": s.work_id,
                    "title": bk.title,
                    "author": bk.authors[0].name if bk.authors else None,
                    "started_at": s.started_at.isoformat(),
                    "finished_at": s.finished_at.isoformat() if s.finished_at else None,
                    "rating": s.rating,
                    "notes": s.notes,
                }
            )

    return {
        "total_books": total_books,
        "books_reading": books_reading,
        "books_completed": books_completed,
        "books_abandoned": books_abandoned,
        "pages_read": pages_read,
        "time_reading_seconds": time_reading,
        "sessions_this_year": sessions_this_year,
        "currently_reading": currently_reading,
        "recently_completed": recently_completed,
        "recent_sessions": recent_sessions,
    }
