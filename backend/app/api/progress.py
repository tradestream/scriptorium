"""Reading progress and statistics API."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.database import get_db
from app.models import Book
from app.models.library import Library
from app.models.progress import Device
from app.models.read_session import ReadSession
from app.models.user import User
from app.models.work import Work

from .auth import assert_edition_access, get_current_user

router = APIRouter()


class ProgressUpdate(BaseModel):
    current_page: int = 0
    total_pages: Optional[int] = None
    percentage: float = 0.0
    file_id: Optional[int] = None
    format: Optional[str] = None
    status: str = "reading"  # want_to_read, reading, completed, abandoned
    rating: Optional[int] = None  # 1-5
    # epubjs CFI of the current paragraph (web reader only). When present
    # we restore the cursor here on the next open instead of falling back
    # to current_page, which is a coarse location estimate.
    cfi: Optional[str] = None
    # Reading-time delta in seconds since the previous progress save in
    # this session. Each reader component runs a small session timer and
    # reports the delta — the server sums it into EditionPosition and
    # ReadingState so total reading time is comparable to Kobo's
    # SpentReadingMinutes counter.
    time_spent_delta_seconds: Optional[int] = None


class StatusUpdate(BaseModel):
    status: Optional[str] = None  # want_to_read, reading, completed, abandoned
    rating: Optional[int] = None  # 1-5, None to clear


def _classify_cursor(
    cfi: Optional[str], percentage: Optional[float]
) -> tuple[str, str]:
    """Disambiguate the wire ``cfi`` field by format.

    The frontend ``ReaderProgress`` reuses the ``cfi`` field for every
    reader. EPUB sends a real CFI; PDF and CBZ/CBR send ``page:N``. The
    unified progress schema has a separate ``page`` format that the rest
    of the stack (Kobo span ↔ CFI conversions, etc.) checks against, so
    storing a page string under ``current_format=cfi`` would let the
    wrong code path try to parse ``"page:14"`` as an epubjs CFI.

    Returns ``(format, value)`` matching ``app.models.reading.FORMAT_*``.
    """
    from app.models.reading import FORMAT_CFI, FORMAT_PAGE, FORMAT_PERCENT

    if cfi:
        if cfi.startswith("page:"):
            return FORMAT_PAGE, cfi.split(":", 1)[1] or "1"
        return FORMAT_CFI, cfi
    return FORMAT_PERCENT, str(percentage or 0)


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
    """Get reading progress for a specific book.

    Reads from the unified progress schema (EditionPosition for cursor /
    pct / total_pages / cfi, ReadingState for lifecycle status / rating
    / timestamps). Response shape preserved for the existing frontend
    consumers.
    """
    from app.models.reading import EditionPosition, ReadingState

    edition = await assert_edition_access(db, current_user, book_id)

    ep = (
        await db.execute(
            select(EditionPosition).where(
                EditionPosition.user_id == current_user.id,
                EditionPosition.edition_id == book_id,
            )
        )
    ).scalar_one_or_none()
    rs = (
        await db.execute(
            select(ReadingState).where(
                ReadingState.user_id == current_user.id,
                ReadingState.work_id == edition.work_id,
            )
        )
    ).scalar_one_or_none()

    if ep is None and rs is None:
        return None

    # The wire ``cfi`` field is format-overloaded: epubjs CFIs, Kobo
    # spans translated to CFIs, and ``page:N`` strings for fixed-layout
    # all flow through it. ``ReaderProgress.savedPage`` parses ``page:N``
    # back into a 1-based number for PdfReader/ComicReader.
    cfi: Optional[str] = None
    if ep and ep.current_format == "cfi":
        cfi = ep.current_value
    elif ep and ep.current_format == "page" and ep.current_value:
        cfi = f"page:{ep.current_value}"
    elif ep and ep.current_format == "kobo_span" and ep.current_value:
        # Cross-device cursor restore: the most recent cursor came from a
        # Kobo device. Translate the koboSpan id back to a partial CFI so
        # the web reader opens at the same chapter (paragraph-accurate
        # would require chapter-XHTML walking; chapter-accurate is what
        # the span map alone supports).
        from app.models.edition import EditionFile
        from app.services.kobo_spans import span_to_cfi

        chapter, _, span_id = ep.current_value.partition("#")
        if chapter and span_id and not span_id.startswith("spine#"):
            epub_file = (
                await db.execute(
                    select(EditionFile).where(
                        EditionFile.edition_id == edition.id,
                        EditionFile.format == "epub",
                    )
                )
            ).scalars().first()
            if epub_file is not None:
                cfi = await span_to_cfi(chapter, span_id, epub_file.id, db)

    pct = (ep.current_pct if ep else 0.0) * 100.0
    total_pages = ep.total_pages if ep else None
    # current_page is a derived display value — frontend uses
    # `pct + cfi`. Approximate from pct × total_pages so any older
    # consumer still gets a sensible integer.
    current_page = int(round((pct / 100.0) * total_pages)) if total_pages else 0

    # Furthest-read watermark for the "Sync to Furthest Position?" UX.
    # The watermark is monotonically non-decreasing (only manual reset
    # regresses it). When it's ahead of the current cursor, the reader
    # surfaces a one-tap "jump to furthest" prompt.
    furthest_pct = (ep.furthest_pct if ep else 0.0) * 100.0
    furthest_cfi: Optional[str] = None
    if ep and ep.furthest_format == "cfi" and ep.furthest_value:
        furthest_cfi = ep.furthest_value
    elif ep and ep.furthest_format == "page" and ep.furthest_value:
        furthest_cfi = f"page:{ep.furthest_value}"
    elif ep and ep.furthest_format == "kobo_span" and ep.furthest_value:
        from app.models.edition import EditionFile
        from app.services.kobo_spans import span_to_cfi

        chapter, _, span_id = ep.furthest_value.partition("#")
        if chapter and span_id and not span_id.startswith("spine#"):
            epub_file = (
                await db.execute(
                    select(EditionFile).where(
                        EditionFile.edition_id == edition.id,
                        EditionFile.format == "epub",
                    )
                )
            ).scalars().first()
            if epub_file is not None:
                furthest_cfi = await span_to_cfi(chapter, span_id, epub_file.id, db)

    return {
        "current_page": current_page,
        "total_pages": total_pages,
        "percentage": pct,
        "status": rs.status if rs else "want_to_read",
        "rating": rs.rating if rs else None,
        "cfi": cfi,
        "last_opened": rs.last_opened.isoformat() if (rs and rs.last_opened) else None,
        "started_at": rs.started_at.isoformat() if (rs and rs.started_at) else None,
        "completed_at": rs.completed_at.isoformat() if (rs and rs.completed_at) else None,
        "furthest_percentage": furthest_pct,
        "furthest_cfi": furthest_cfi,
    }


@router.post("/books/{book_id}/progress/reset-furthest", status_code=status.HTTP_200_OK)
async def reset_furthest_position(
    book_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reset the furthest-read watermark on this edition for the current user.

    Per the design (`personal/design/unified_progress_schema.md` §8.4),
    furthest-read is monotonic non-decreasing in normal sync — only
    this explicit user action regresses it. Useful for re-reads on
    shared accounts so the "Sync to furthest" prompt doesn't keep
    pulling the new reader to where the previous reader stopped.

    The watermark is dropped to the current cursor's pct (not to zero —
    if you're partway through a re-read, that's where furthest should
    be). ``furthest_reset_at`` records the audit trail.
    """
    from app.models.reading import EditionPosition

    await assert_edition_access(db, current_user, book_id)

    ep = (
        await db.execute(
            select(EditionPosition).where(
                EditionPosition.user_id == current_user.id,
                EditionPosition.edition_id == book_id,
            )
        )
    ).scalar_one_or_none()
    if ep is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No progress to reset")

    now = datetime.utcnow()
    ep.furthest_format = ep.current_format
    ep.furthest_value = ep.current_value
    ep.furthest_pct = ep.current_pct or 0.0
    ep.furthest_updated_at = now
    ep.furthest_reset_at = now
    await db.commit()
    return {"ok": True, "furthest_pct": (ep.furthest_pct or 0.0) * 100.0}


@router.put("/books/{book_id}/progress")
async def update_book_progress(
    book_id: int,
    data: ProgressUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upsert reading progress for a book (web reader auto-saves here).

    Writes only into the unified progress schema (EditionPosition +
    ReadingState + DevicePosition) via the shared write_progress helper.
    The legacy ReadProgress dual-write was removed in step 4 of the
    progress migration; see personal/design/unified_progress_schema.md.
    """
    from app.services.unified_progress import write_progress

    edition = await assert_edition_access(db, current_user, book_id)

    device = await _get_or_create_web_device(db, current_user.id)
    now = datetime.utcnow()

    cursor_pct = (data.percentage or 0) / 100.0
    cursor_format, cursor_value = _classify_cursor(data.cfi, data.percentage)

    await write_progress(
        db,
        user_id=current_user.id,
        edition=edition,
        cursor_format=cursor_format,
        cursor_value=cursor_value,
        cursor_pct=cursor_pct,
        device_id=device.id,
        total_pages=data.total_pages,
        time_spent_delta_seconds=max(0, data.time_spent_delta_seconds or 0),
        status_hint=data.status if data.status in ("completed", "abandoned") else None,
        rating=data.rating,
        timestamp=now,
    )

    await db.commit()
    return {"ok": True}


@router.patch("/books/{book_id}/progress")
async def patch_book_status(
    book_id: int,
    data: StatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Set reading status and/or rating without touching reading position.

    Routes through the unified write_progress helper, which handles the
    status-transition rules (e.g. setting started_at on first ``reading``
    transition, bumping times_completed on ``completed``). Rating updates
    apply to ReadingState; an explicit ``None`` clears the rating.
    """
    from app.models.reading import EditionPosition, ReadingState
    from app.services.unified_progress import write_progress

    edition = await assert_edition_access(db, current_user, book_id)

    device = await _get_or_create_web_device(db, current_user.id)
    now = datetime.utcnow()

    # Read the existing cursor so we can pass through pct unchanged when the
    # caller is just toggling status / rating.
    ep = (
        await db.execute(
            select(EditionPosition).where(
                EditionPosition.user_id == current_user.id,
                EditionPosition.edition_id == book_id,
            )
        )
    ).scalar_one_or_none()
    cursor_pct = ep.current_pct if ep else 0.0
    cursor_format = ep.current_format if ep else "percent"
    cursor_value = ep.current_value if ep else "0"

    rating = data.rating
    if rating is not None:
        rating = max(1, min(5, rating))

    await write_progress(
        db,
        user_id=current_user.id,
        edition=edition,
        cursor_format=cursor_format,
        cursor_value=cursor_value,
        cursor_pct=cursor_pct,
        device_id=device.id,
        status_hint=data.status,
        rating=rating,
        timestamp=now,
    )

    # Explicit-None rating clears — write_progress doesn't apply None as
    # a clear, so handle that case directly on ReadingState.
    if rating is None and "rating" in (data.model_fields_set or set()):
        rs = (
            await db.execute(
                select(ReadingState).where(
                    ReadingState.user_id == current_user.id,
                    ReadingState.work_id == edition.work_id,
                )
            )
        ).scalar_one_or_none()
        if rs is not None:
            rs.rating = None

    await db.commit()
    return {"ok": True}


@router.get("/stats")
async def get_reading_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reading statistics for the current user (work-keyed, hidden-aware)."""
    from app.models.reading import EditionPosition, ReadingState

    uid = current_user.id

    # Status counts: ReadingState rows whose work has at least one Edition
    # in a non-hidden library. The DISTINCT on Work prevents double-counting
    # if a Work has multiple visible editions.
    async def count_status(s: str) -> int:
        r = await db.scalar(
            select(func.count(func.distinct(ReadingState.work_id)))
            .join(Book, Book.work_id == ReadingState.work_id)
            .join(Library, Library.id == Book.library_id)
            .where(
                ReadingState.user_id == uid,
                ReadingState.status == s,
                Library.is_hidden == False,
            )
        )
        return r or 0

    books_reading = await count_status("reading")
    books_completed = await count_status("completed")
    books_abandoned = await count_status("abandoned")

    # Pages read: derive from EditionPosition.current_pct × total_pages
    # for each visible edition the user has progress on.
    rows = (
        await db.execute(
            select(EditionPosition.current_pct, EditionPosition.total_pages)
            .join(Book, Book.id == EditionPosition.edition_id)
            .join(Library, Library.id == Book.library_id)
            .where(EditionPosition.user_id == uid, Library.is_hidden == False)
        )
    ).all()
    pages_read = sum(
        int(round((pct or 0.0) * pages))
        for pct, pages in rows
        if pages
    )

    # Time spent reading: prefer the work-level total when available
    # (web reader session timer + Kobo deltas both feed this).
    time_reading = await db.scalar(
        select(func.sum(ReadingState.total_time_seconds)).where(
            ReadingState.user_id == uid
        )
    ) or 0

    # Total books in library (exclude hidden)
    total_books = await db.scalar(
        select(func.count(Book.id))
        .join(Library, Library.id == Book.library_id)
        .where(Library.is_hidden == False)
    ) or 0

    # Currently reading (most recently opened, up to 5, exclude hidden).
    # We pick one canonical Edition per Work for display.
    reading_rs = (
        await db.execute(
            select(ReadingState)
            .where(ReadingState.user_id == uid, ReadingState.status == "reading")
            .order_by(ReadingState.last_opened.desc().nulls_last())
            .limit(5)
        )
    ).scalars().all()

    async def _display_row(rs: ReadingState) -> dict | None:
        ed_row = await db.execute(
            select(Book)
            .join(Library, Library.id == Book.library_id)
            .where(Book.work_id == rs.work_id, Library.is_hidden == False)
            .options(joinedload(Book.work).options(joinedload(Work.authors)))
            .limit(1)
        )
        book = ed_row.unique().scalar_one_or_none()
        if book is None:
            return None
        ep = (
            await db.execute(
                select(EditionPosition).where(
                    EditionPosition.user_id == uid,
                    EditionPosition.edition_id == book.id,
                )
            )
        ).scalar_one_or_none()
        return {
            "id": book.id,
            "title": book.title,
            "author": book.authors[0].name if book.authors else None,
            "percentage": round((ep.current_pct if ep else 0.0) * 100.0, 1),
            "last_opened": rs.last_opened.isoformat() if rs.last_opened else None,
            "completed_at": rs.completed_at.isoformat() if rs.completed_at else None,
        }

    currently_reading = []
    for rs in reading_rs:
        row = await _display_row(rs)
        if row is not None:
            row.pop("completed_at", None)
            currently_reading.append(row)

    # Recently completed (up to 5, exclude hidden)
    completed_rs = (
        await db.execute(
            select(ReadingState)
            .where(ReadingState.user_id == uid, ReadingState.status == "completed")
            .order_by(ReadingState.completed_at.desc().nulls_last())
            .limit(5)
        )
    ).scalars().all()
    recently_completed = []
    for rs in completed_rs:
        row = await _display_row(rs)
        if row is not None:
            row.pop("percentage", None)
            row.pop("last_opened", None)
            recently_completed.append(row)

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
