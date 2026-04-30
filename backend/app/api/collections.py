import json as _json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.database import get_db
from app.models import User
from app.models.book import Author, Book, Series, Tag
from app.models.collection import Collection, CollectionBook
from app.models.edition import Edition, EditionFile
from app.models.work import Work
from app.schemas.book import BookRead
from app.schemas.collection import (
    CollectionBookAdd,
    CollectionCreate,
    CollectionDetail,
    CollectionRead,
    CollectionUpdate,
)

router = APIRouter(prefix="/collections", tags=["collections"])


def _build_smart_query(filters: dict, user_id: int):
    """Build a SQLAlchemy query for a smart collection's filter rules."""
    from app.api.books import _edition_options

    stmt = select(Edition).join(Edition.work).options(*_edition_options())

    if filters.get("library_id"):
        stmt = stmt.where(Edition.library_id == filters["library_id"])
    if filters.get("author"):
        stmt = stmt.where(Work.authors.any(Author.name.ilike(f"%{filters['author']}%")))
    if filters.get("tag"):
        stmt = stmt.where(Work.tags.any(Tag.name == filters["tag"]))
    if filters.get("series"):
        stmt = stmt.where(Work.series.any(Series.name.ilike(f"%{filters['series']}%")))
    if filters.get("format"):
        stmt = stmt.where(Edition.files.any(EditionFile.format.ilike(filters["format"])))
    if filters.get("language"):
        stmt = stmt.where(or_(Edition.language == filters["language"], Work.language == filters["language"]))
    if filters.get("physical_copy") is not None:
        stmt = stmt.where(Edition.physical_copy == filters["physical_copy"])
    if filters.get("binding"):
        stmt = stmt.where(Edition.binding == filters["binding"])
    if filters.get("condition"):
        stmt = stmt.where(Edition.condition == filters["condition"])
    if filters.get("has_isbn") is True:
        stmt = stmt.where(Edition.isbn.isnot(None))
    elif filters.get("has_isbn") is False:
        stmt = stmt.where(Edition.isbn.is_(None))
    if filters.get("status"):
        from app.models.reading import ReadingState
        stmt = stmt.where(
            Edition.work_id.in_(
                select(ReadingState.work_id).where(
                    ReadingState.user_id == user_id,
                    ReadingState.status == filters["status"],
                )
            )
        )
    if filters.get("min_rating"):
        from app.models.reading import ReadingState
        stmt = stmt.where(
            Edition.work_id.in_(
                select(ReadingState.work_id).where(
                    ReadingState.user_id == user_id,
                    ReadingState.rating >= filters["min_rating"],
                )
            )
        )

    return stmt.order_by(Work.title.asc())


async def _get_collection_or_404(collection_id: int, user_id: int, db: AsyncSession) -> Collection:
    result = await db.execute(
        select(Collection).where(Collection.id == collection_id, Collection.user_id == user_id)
    )
    collection = result.scalar_one_or_none()
    if not collection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")
    return collection


@router.get("", response_model=list[CollectionRead])
async def list_collections(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Collection)
        .where(Collection.user_id == current_user.id)
        .order_by(Collection.updated_at.desc())
    )
    collections = result.scalars().all()
    out = []
    for col in collections:
        item = CollectionRead.model_validate(col)
        # Parse smart_filter JSON string for response
        if col.smart_filter:
            try:
                item.smart_filter = _json.loads(col.smart_filter)
            except Exception:
                item.smart_filter = None

        if col.is_smart and col.smart_filter:
            # Count via dynamic query
            try:
                filters = _json.loads(col.smart_filter)
                count_stmt = select(func.count()).select_from(
                    _build_smart_query(filters, current_user.id).subquery()
                )
                item.book_count = (await db.scalar(count_stmt)) or 0
            except Exception:
                item.book_count = 0
        else:
            count_result = await db.execute(
                select(func.count()).where(CollectionBook.collection_id == col.id)
            )
            item.book_count = count_result.scalar() or 0
        out.append(item)
    return out


@router.post("", response_model=CollectionRead, status_code=status.HTTP_201_CREATED)
async def create_collection(
    data: CollectionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    collection = Collection(
        user_id=current_user.id,
        name=data.name.strip(),
        description=data.description,
        is_smart=data.is_smart,
        is_pinned=data.is_pinned,
        sync_to_kobo=data.sync_to_kobo,
        smart_filter=data.smart_filter.model_dump_json() if data.smart_filter else None,
        cover_work_id=data.cover_work_id,
    )
    db.add(collection)
    await db.commit()
    await db.refresh(collection)
    item = CollectionRead.model_validate(collection)
    item.book_count = 0
    return item


@router.get("/{collection_id}", response_model=CollectionDetail)
async def get_collection(
    collection_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    collection = await _get_collection_or_404(collection_id, current_user.id, db)
    detail = CollectionDetail.model_validate(collection)
    if collection.smart_filter:
        try:
            detail.smart_filter = _json.loads(collection.smart_filter)
        except Exception:
            detail.smart_filter = None

    if collection.is_smart and collection.smart_filter:
        # Dynamic query from smart filter
        try:
            filters = _json.loads(collection.smart_filter)
            stmt = _build_smart_query(filters, current_user.id).limit(500)
            result = await db.execute(stmt)
            editions = result.unique().scalars().all()
            detail.books = [BookRead.model_validate(e) for e in editions]
            detail.book_count = len(detail.books)
        except Exception:
            detail.books = []
            detail.book_count = 0
    else:
        # Manual collection — ordered entries
        entries_result = await db.execute(
            select(CollectionBook)
            .where(CollectionBook.collection_id == collection_id)
            .order_by(CollectionBook.position)
        )
        entries = entries_result.scalars().all()
        book_ids = [e.work_id for e in entries]
        books_map: dict[int, Book] = {}
        if book_ids:
            from app.api.books import _edition_options
            books_result = await db.execute(
                select(Book).options(*_edition_options()).where(Book.id.in_(book_ids))
            )
            for book in books_result.unique().scalars().all():
                books_map[book.id] = book
        detail.books = [BookRead.model_validate(books_map[bid]) for bid in book_ids if bid in books_map]
        detail.book_count = len(detail.books)

    return detail


@router.put("/{collection_id}", response_model=CollectionRead)
async def update_collection(
    collection_id: int,
    data: CollectionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    collection = await _get_collection_or_404(collection_id, current_user.id, db)
    if data.name is not None:
        collection.name = data.name.strip()
    if data.description is not None:
        collection.description = data.description
    if data.cover_work_id is not None:
        collection.cover_work_id = data.cover_work_id
    if data.is_smart is not None:
        collection.is_smart = data.is_smart
    if data.is_pinned is not None:
        collection.is_pinned = data.is_pinned
    if data.sync_to_kobo is not None:
        collection.sync_to_kobo = data.sync_to_kobo
    if data.smart_filter is not None:
        collection.smart_filter = data.smart_filter.model_dump_json()
    await db.commit()
    await db.refresh(collection)
    count_result = await db.execute(
        select(func.count()).where(CollectionBook.collection_id == collection_id)
    )
    item = CollectionRead.model_validate(collection)
    item.book_count = count_result.scalar() or 0
    return item


@router.delete("/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_collection(
    collection_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    collection = await _get_collection_or_404(collection_id, current_user.id, db)
    await db.delete(collection)
    await db.commit()


@router.post("/{collection_id}/books", status_code=status.HTTP_204_NO_CONTENT)
async def add_book_to_collection(
    collection_id: int,
    data: CollectionBookAdd,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_collection_or_404(collection_id, current_user.id, db)
    exists = await db.execute(
        select(CollectionBook).where(
            and_(CollectionBook.collection_id == collection_id, CollectionBook.work_id == data.book_id)
        )
    )
    if exists.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Book already in collection")
    if data.position is not None:
        position = data.position
    else:
        max_result = await db.execute(
            select(func.max(CollectionBook.position)).where(CollectionBook.collection_id == collection_id)
        )
        position = (max_result.scalar() or -1) + 1
    db.add(CollectionBook(collection_id=collection_id, work_id=data.book_id, position=position))
    await db.commit()


@router.delete("/{collection_id}/books/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_book_from_collection(
    collection_id: int,
    book_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_collection_or_404(collection_id, current_user.id, db)
    result = await db.execute(
        select(CollectionBook).where(
            and_(CollectionBook.collection_id == collection_id, CollectionBook.work_id == book_id)
        )
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not in collection")
    await db.delete(entry)
    await db.commit()
