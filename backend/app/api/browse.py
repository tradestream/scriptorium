"""Browse endpoints for authors, tags, series, and dynamic covers."""

from typing import Optional

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.database import get_db
from app.models import Author, Series, Tag, User
from app.models.edition import Edition, UserEdition
from app.models.library import Library
from app.models.work import Work, work_authors, work_series, work_tags
from app.schemas.book import BookRead

from .auth import get_accessible_library_ids, get_current_user

router = APIRouter()


def _edition_options():
    return [
        joinedload(Edition.work).options(
            joinedload(Work.authors),
            joinedload(Work.tags),
            joinedload(Work.series),
            joinedload(Work.contributors),
        ),
        joinedload(Edition.files),
        joinedload(Edition.contributors),
    ]


class AuthorDetail(BaseModel):
    id: int
    name: str
    description: str | None = None
    photo_url: str | None = None
    book_count: int

    class Config:
        from_attributes = True


class TagDetail(BaseModel):
    id: int
    name: str
    book_count: int

    class Config:
        from_attributes = True


class SeriesDetail(BaseModel):
    id: int
    name: str
    description: str | None = None
    book_count: int
    cover_book_id: int | None = None   # edition ID to use for cover thumbnail

    class Config:
        from_attributes = True


# ── Authors ──────────────────────────────────────────────────────────────────

@router.get("/authors", response_model=list[AuthorDetail], tags=["browse"])
async def list_authors(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all authors with their work counts, alphabetically."""
    accessible_ids = await get_accessible_library_ids(db, current_user)
    visible_lib_ids = select(Library.id).where(Library.is_hidden == False)

    stmt = (
        select(Author, func.count(func.distinct(Work.id)).label("book_count"))
        .outerjoin(work_authors, work_authors.c.author_id == Author.id)
        .outerjoin(Work, Work.id == work_authors.c.work_id)
        .outerjoin(Edition, Edition.work_id == Work.id)
        .group_by(Author.id)
        .order_by(Author.name)
        .limit(limit)
        .offset(skip)
    )
    stmt = stmt.where((Edition.library_id.in_(visible_lib_ids)) | (Edition.id.is_(None)))
    if accessible_ids is not None:
        stmt = stmt.where((Edition.library_id.in_(accessible_ids)) | (Edition.id.is_(None)))

    rows = await db.execute(stmt)
    return [
        AuthorDetail(id=author.id, name=author.name, description=author.description, photo_url=author.photo_url, book_count=count)
        for author, count in rows
    ]


@router.get("/authors/{author_id}", tags=["browse"])
async def get_author(
    author_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get an author and their books."""
    result = await db.execute(select(Author).where(Author.id == author_id))
    author = result.scalar_one_or_none()
    if not author:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Author not found")

    accessible_ids = await get_accessible_library_ids(db, current_user)
    visible_lib_ids = select(Library.id).where(Library.is_hidden == False)

    books_stmt = (
        select(Edition)
        .join(Edition.work)
        .where(Work.authors.any(id=author_id))
        .where(Edition.library_id.in_(visible_lib_ids))
        .options(*_edition_options())
        .order_by(Work.title)
        .limit(limit)
        .offset(skip)
    )
    count_stmt = (
        select(func.count(Edition.id))
        .join(Edition.work)
        .where(Work.authors.any(id=author_id))
        .where(Edition.library_id.in_(visible_lib_ids))
    )
    if accessible_ids is not None:
        books_stmt = books_stmt.where(Edition.library_id.in_(accessible_ids))
        count_stmt = count_stmt.where(Edition.library_id.in_(accessible_ids))

    books_result = await db.execute(books_stmt)
    editions = books_result.unique().scalars().all()
    count = await db.scalar(count_stmt)

    return {
        "id": author.id,
        "name": author.name,
        "description": author.description,
        "book_count": count or 0,
        "books": [BookRead.model_validate(e) for e in editions],
        "skip": skip,
        "limit": limit,
    }


# ── Tags ──────────────────────────────────────────────────────────────────────

@router.get("/tags", response_model=list[TagDetail], tags=["browse"])
async def list_tags(
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all tags with their work counts, alphabetically."""
    accessible_ids = await get_accessible_library_ids(db, current_user)
    visible_lib_ids = select(Library.id).where(Library.is_hidden == False)

    stmt = (
        select(Tag, func.count(func.distinct(Work.id)).label("book_count"))
        .outerjoin(work_tags, work_tags.c.tag_id == Tag.id)
        .outerjoin(Work, Work.id == work_tags.c.work_id)
        .outerjoin(Edition, Edition.work_id == Work.id)
        .group_by(Tag.id)
        .order_by(Tag.name)
        .limit(limit)
        .offset(skip)
    )
    stmt = stmt.where((Edition.library_id.in_(visible_lib_ids)) | (Edition.id.is_(None)))
    if accessible_ids is not None:
        stmt = stmt.where((Edition.library_id.in_(accessible_ids)) | (Edition.id.is_(None)))

    rows = await db.execute(stmt)
    return [
        TagDetail(id=tag.id, name=tag.name, book_count=count)
        for tag, count in rows
    ]


@router.get("/tags/{tag_id}", tags=["browse"])
async def get_tag(
    tag_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a tag and its books."""
    result = await db.execute(select(Tag).where(Tag.id == tag_id))
    tag = result.scalar_one_or_none()
    if not tag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")

    accessible_ids = await get_accessible_library_ids(db, current_user)
    visible_lib_ids = select(Library.id).where(Library.is_hidden == False)

    books_stmt = (
        select(Edition)
        .join(Edition.work)
        .where(Work.tags.any(id=tag_id))
        .where(Edition.library_id.in_(visible_lib_ids))
        .options(*_edition_options())
        .order_by(Work.title)
        .limit(limit)
        .offset(skip)
    )
    count_stmt = (
        select(func.count(Edition.id))
        .join(Edition.work)
        .where(Work.tags.any(id=tag_id))
        .where(Edition.library_id.in_(visible_lib_ids))
    )
    if accessible_ids is not None:
        books_stmt = books_stmt.where(Edition.library_id.in_(accessible_ids))
        count_stmt = count_stmt.where(Edition.library_id.in_(accessible_ids))

    books_result = await db.execute(books_stmt)
    editions = books_result.unique().scalars().all()
    count = await db.scalar(count_stmt)

    return {
        "id": tag.id,
        "name": tag.name,
        "book_count": count or 0,
        "books": [BookRead.model_validate(e) for e in editions],
        "skip": skip,
        "limit": limit,
    }


# ── Series ────────────────────────────────────────────────────────────────────

@router.get("/series", response_model=list[SeriesDetail], tags=["browse"])
async def list_series(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    library_id: Optional[int] = None,
    format: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all series with their work counts, alphabetically.

    Optional filters:
    - library_id: only series with books in this library
    - format: only series with books having files in this format (e.g. cbz, epub)
    """
    accessible_ids = await get_accessible_library_ids(db, current_user)
    visible_lib_ids = select(Library.id).where(Library.is_hidden == False)

    stmt = (
        select(Series, func.count(func.distinct(Work.id)).label("book_count"))
        .outerjoin(work_series, work_series.c.series_id == Series.id)
        .outerjoin(Work, Work.id == work_series.c.work_id)
        .outerjoin(Edition, Edition.work_id == Work.id)
        .group_by(Series.id)
        .order_by(Series.name)
        .limit(limit)
        .offset(skip)
    )

    if library_id:
        stmt = stmt.where(Edition.library_id == library_id)
    else:
        stmt = stmt.where((Edition.library_id.in_(visible_lib_ids)) | (Edition.id.is_(None)))

    if format:
        from app.models.edition import EditionFile
        stmt = stmt.where(Edition.files.any(EditionFile.format.ilike(format)))

    if accessible_ids is not None:
        stmt = stmt.where((Edition.library_id.in_(accessible_ids)) | (Edition.id.is_(None)))

    rows = await db.execute(stmt)
    results = list(rows)
    series_ids = [s.id for s, _ in results]

    # Fetch one edition per series that has a cover (for thumbnail)
    cover_map: dict[int, int] = {}
    if series_ids:
        cover_stmt = (
            select(work_series.c.series_id, func.min(Edition.id).label("edition_id"))
            .join(Work, Work.id == work_series.c.work_id)
            .join(Edition, Edition.work_id == Work.id)
            .where(work_series.c.series_id.in_(series_ids))
            .where(Edition.cover_hash.isnot(None))
            .group_by(work_series.c.series_id)
        )
        for sid, eid in await db.execute(cover_stmt):
            cover_map[sid] = eid

    return [
        SeriesDetail(
            id=s.id, name=s.name, description=s.description,
            book_count=count, cover_book_id=cover_map.get(s.id),
        )
        for s, count in results
    ]


@router.get("/series/{series_id}", tags=["browse"])
async def get_series(
    series_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a series with all its books, including position/volume/arc metadata and read status."""
    result = await db.execute(select(Series).where(Series.id == series_id))
    series = result.scalar_one_or_none()
    if not series:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Series not found")

    accessible_ids = await get_accessible_library_ids(db, current_user)
    visible_lib_ids = select(Library.id).where(Library.is_hidden == False)

    # Fetch editions via their work's series membership
    books_stmt = (
        select(Edition, work_series.c.position, work_series.c.volume, work_series.c.arc)
        .join(Edition.work)
        .join(work_series, (work_series.c.work_id == Work.id) & (work_series.c.series_id == series_id))
        .where(Edition.library_id.in_(visible_lib_ids))
        .options(*_edition_options())
        .order_by(
            work_series.c.volume.nullslast(),
            work_series.c.position.nullslast(),
            Edition.published_date.nullslast(),
            Work.title,
        )
    )
    if accessible_ids is not None:
        books_stmt = books_stmt.where(Edition.library_id.in_(accessible_ids))

    books_result = await db.execute(books_stmt)
    rows = books_result.unique().all()

    # Fetch read status from the unified ReadingState (work-keyed).
    from app.models.reading import ReadingState
    edition_ids = [r[0].id for r in rows]
    read_status: dict[int, str] = {}
    if edition_ids:
        rs_result = await db.execute(
            select(Edition.id, ReadingState.status)
            .join(ReadingState, ReadingState.work_id == Edition.work_id)
            .where(ReadingState.user_id == current_user.id)
            .where(Edition.id.in_(edition_ids))
        )
        for ed_id, st in rs_result:
            current = read_status.get(ed_id)
            if current != "completed":
                read_status[ed_id] = st

    entries = [
        {
            "book": BookRead.model_validate(edition),
            "position": position,
            "volume": volume,
            "arc": arc,
            "read_status": read_status.get(edition.id),
        }
        for edition, position, volume, arc in rows
    ]

    return {
        "id": series.id,
        "name": series.name,
        "description": series.description,
        "book_count": len(entries),
        "entries": entries,
    }


class SeriesEntryUpdate(BaseModel):
    book_id: int           # edition ID (frontend sends edition ID as "book_id")
    position: float | None = None
    volume: str | None = None
    arc: str | None = None


@router.patch("/series/{series_id}/entries", status_code=204, tags=["browse"])
async def update_series_entries(
    series_id: int,
    entries: list[SeriesEntryUpdate],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Batch-update position/volume/arc for entries in a series. Admin only."""
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")

    result = await db.execute(select(Series).where(Series.id == series_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Series not found")

    # Resolve edition IDs → work IDs
    edition_ids = [e.work_id for e in entries]
    ed_result = await db.execute(
        select(Edition.id, Edition.work_id).where(Edition.id.in_(edition_ids))
    )
    edition_to_work = {ed_id: work_id for ed_id, work_id in ed_result}

    for entry in entries:
        work_id = edition_to_work.get(entry.work_id)
        if not work_id:
            continue
        await db.execute(
            update(work_series)
            .where(
                (work_series.c.series_id == series_id) &
                (work_series.c.work_id == work_id)
            )
            .values(
                position=entry.position,
                volume=entry.volume if entry.volume != "" else None,
                arc=entry.arc if entry.arc != "" else None,
            )
        )

    await db.commit()


# ── Dynamic covers (first-in-group pattern) ────────────────────────────────

async def _group_cover(db: AsyncSession, stmt):
    """Return the cover of the first edition with a cover in a group query."""
    from app.config import get_settings
    result = await db.execute(stmt)
    edition = result.scalar_one_or_none()
    if not edition or not edition.cover_hash:
        raise HTTPException(status_code=404, detail="No cover available")

    settings = get_settings()
    cover_path = Path(settings.COVERS_PATH) / f"{edition.uuid}.{edition.cover_format}"
    if not cover_path.exists():
        raise HTTPException(status_code=404, detail="Cover file not found")

    return FileResponse(str(cover_path), media_type=f"image/{edition.cover_format}")


@router.get("/series/{series_id}/cover", tags=["browse"])
async def series_cover(
    series_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Dynamic cover for a series — returns the first book's cover."""
    from app.models import Series
    from app.models.work import work_series
    stmt = (
        select(Edition)
        .join(work_series, work_series.c.work_id == Edition.work_id)
        .where(work_series.c.series_id == series_id, Edition.cover_hash.isnot(None))
        .order_by(Edition.created_at)
        .limit(1)
    )
    return await _group_cover(db, stmt)


@router.get("/authors/{author_id}/cover", tags=["browse"])
async def author_cover(
    author_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Dynamic cover for an author — returns the first book's cover."""
    from app.models.work import work_authors
    stmt = (
        select(Edition)
        .join(work_authors, work_authors.c.work_id == Edition.work_id)
        .where(work_authors.c.author_id == author_id, Edition.cover_hash.isnot(None))
        .order_by(Edition.created_at)
        .limit(1)
    )
    return await _group_cover(db, stmt)
