from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api.auth import get_current_user
from app.database import get_db
from app.models import User
from app.models.book import Book
from app.models.collection import Collection, CollectionBook
from app.schemas.book import BookRead
from app.schemas.collection import (
    CollectionBookAdd,
    CollectionCreate,
    CollectionDetail,
    CollectionRead,
    CollectionUpdate,
)

router = APIRouter(prefix="/collections", tags=["collections"])


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
        count_result = await db.execute(
            select(func.count()).where(CollectionBook.collection_id == col.id)
        )
        item = CollectionRead.model_validate(col)
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
        cover_book_id=data.cover_book_id,
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
    entries_result = await db.execute(
        select(CollectionBook)
        .where(CollectionBook.collection_id == collection_id)
        .order_by(CollectionBook.position)
    )
    entries = entries_result.scalars().all()
    book_ids = [e.book_id for e in entries]
    books_map: dict[int, Book] = {}
    if book_ids:
        books_result = await db.execute(
            select(Book)
            .options(
                joinedload(Book.authors),
                joinedload(Book.tags),
                joinedload(Book.series),
                joinedload(Book.files),
                joinedload(Book.contributors),
            )
            .where(Book.id.in_(book_ids))
        )
        for book in books_result.unique().scalars().all():
            books_map[book.id] = book

    ordered_books = [BookRead.model_validate(books_map[bid]) for bid in book_ids if bid in books_map]
    detail = CollectionDetail.model_validate(collection)
    detail.book_count = len(ordered_books)
    detail.books = ordered_books
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
    if data.cover_book_id is not None:
        collection.cover_book_id = data.cover_book_id
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
            and_(CollectionBook.collection_id == collection_id, CollectionBook.book_id == data.book_id)
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
    db.add(CollectionBook(collection_id=collection_id, book_id=data.book_id, position=position))
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
            and_(CollectionBook.collection_id == collection_id, CollectionBook.book_id == book_id)
        )
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not in collection")
    await db.delete(entry)
    await db.commit()
