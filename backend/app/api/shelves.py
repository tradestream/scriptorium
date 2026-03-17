from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.database import get_db
from app.models import Author, Book, Series, Shelf, ShelfBook, Tag, User
from app.models.progress import ReadProgress
from app.schemas.shelf import ShelfBookAdd, ShelfCreate, ShelfRead, ShelfUpdate

from .auth import get_current_user

router = APIRouter(prefix="/shelves")


async def _shelf_book_count(db: AsyncSession, shelf_id: int) -> int:
    count = await db.scalar(
        select(func.count(ShelfBook.id)).where(ShelfBook.shelf_id == shelf_id)
    )
    return count or 0


@router.get("", response_model=list[ShelfRead])
async def list_shelves(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all shelves for current user."""
    stmt = (
        select(Shelf)
        .where(Shelf.user_id == current_user.id)
        .order_by(Shelf.created_at.desc())
    )
    result = await db.execute(stmt)
    shelves = result.scalars().all()

    shelf_list = []
    for shelf in shelves:
        shelf_read = ShelfRead.model_validate(shelf)
        shelf_read.book_count = await _shelf_book_count(db, shelf.id)
        shelf_list.append(shelf_read)

    return shelf_list


@router.get("/{shelf_id}", response_model=ShelfRead)
async def get_shelf(
    shelf_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific shelf."""
    stmt = select(Shelf).where(
        and_(Shelf.id == shelf_id, Shelf.user_id == current_user.id)
    )
    result = await db.execute(stmt)
    shelf = result.scalar_one_or_none()

    if not shelf:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shelf not found",
        )

    shelf_read = ShelfRead.model_validate(shelf)
    shelf_read.book_count = await _shelf_book_count(db, shelf.id)

    return shelf_read


@router.post("", response_model=ShelfRead, status_code=status.HTTP_201_CREATED)
async def create_shelf(
    shelf_data: ShelfCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new shelf."""
    shelf = Shelf(
        user_id=current_user.id,
        name=shelf_data.name,
        description=shelf_data.description,
        is_smart=shelf_data.is_smart,
        smart_filter=shelf_data.smart_filter,
    )

    db.add(shelf)
    await db.commit()
    await db.refresh(shelf)

    shelf_read = ShelfRead.model_validate(shelf)
    shelf_read.book_count = 0

    return shelf_read


@router.put("/{shelf_id}", response_model=ShelfRead)
async def update_shelf(
    shelf_id: int,
    shelf_data: ShelfUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a shelf."""
    stmt = select(Shelf).where(
        and_(Shelf.id == shelf_id, Shelf.user_id == current_user.id)
    )
    result = await db.execute(stmt)
    shelf = result.scalar_one_or_none()

    if not shelf:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shelf not found",
        )

    if shelf_data.name is not None:
        shelf.name = shelf_data.name

    if shelf_data.description is not None:
        shelf.description = shelf_data.description

    if shelf_data.is_smart is not None:
        shelf.is_smart = shelf_data.is_smart

    if shelf_data.smart_filter is not None:
        shelf.smart_filter = shelf_data.smart_filter

    await db.commit()
    await db.refresh(shelf)

    shelf_read = ShelfRead.model_validate(shelf)
    shelf_read.book_count = await _shelf_book_count(db, shelf.id)

    return shelf_read


@router.delete("/{shelf_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_shelf(
    shelf_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a shelf."""
    stmt = select(Shelf).where(
        and_(Shelf.id == shelf_id, Shelf.user_id == current_user.id)
    )
    result = await db.execute(stmt)
    shelf = result.scalar_one_or_none()

    if not shelf:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shelf not found",
        )

    await db.delete(shelf)
    await db.commit()


@router.post("/{shelf_id}/books", status_code=status.HTTP_200_OK)
async def add_book_to_shelf(
    shelf_id: int,
    data: ShelfBookAdd,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a book to a shelf."""
    # Verify shelf belongs to user
    stmt = select(Shelf).where(
        and_(Shelf.id == shelf_id, Shelf.user_id == current_user.id)
    )
    result = await db.execute(stmt)
    shelf = result.scalar_one_or_none()

    if not shelf:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shelf not found",
        )

    # Verify book exists
    stmt = select(Book).where(Book.id == data.book_id)
    result = await db.execute(stmt)
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Book not found",
        )

    # Check if already on shelf
    stmt = select(ShelfBook).where(
        and_(ShelfBook.shelf_id == shelf_id, ShelfBook.work_id == data.book_id)
    )
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Book already on shelf",
        )

    # Get next position
    position = await _shelf_book_count(db, shelf_id)

    shelf_book = ShelfBook(
        shelf_id=shelf_id,
        book_id=data.book_id,
        position=position,
    )

    db.add(shelf_book)
    await db.commit()

    return {"status": "ok", "message": "Book added to shelf"}


@router.delete("/{shelf_id}/books/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_book_from_shelf(
    shelf_id: int,
    book_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a book from a shelf."""
    # Verify shelf belongs to user
    stmt = select(Shelf).where(
        and_(Shelf.id == shelf_id, Shelf.user_id == current_user.id)
    )
    result = await db.execute(stmt)
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shelf not found",
        )

    # Find and delete shelf_book
    stmt = select(ShelfBook).where(
        and_(ShelfBook.shelf_id == shelf_id, ShelfBook.work_id == book_id)
    )
    result = await db.execute(stmt)
    shelf_book = result.scalar_one_or_none()

    if not shelf_book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Book not on shelf",
        )

    await db.delete(shelf_book)
    await db.commit()


class BulkShelfRequest(BaseModel):
    """Bulk shelf assignment/unassignment."""
    book_ids: list[int]
    shelves_to_assign: list[int] = []
    shelves_to_unassign: list[int] = []


@router.post("/bulk", status_code=status.HTTP_200_OK)
async def bulk_shelf_assignment(
    req: BulkShelfRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Assign/unassign multiple books to/from shelves in a single request."""
    # Verify all shelves belong to user
    if req.shelves_to_assign or req.shelves_to_unassign:
        all_shelf_ids = set(req.shelves_to_assign + req.shelves_to_unassign)
        result = await db.execute(
            select(Shelf).where(Shelf.id.in_(all_shelf_ids), Shelf.user_id == current_user.id)
        )
        found_ids = {s.id for s in result.scalars().all()}
        missing = all_shelf_ids - found_ids
        if missing:
            raise HTTPException(status_code=404, detail=f"Shelves not found: {missing}")

    assigned = 0
    unassigned = 0

    for book_id in req.book_ids:
        # Assignments
        for shelf_id in req.shelves_to_assign:
            existing = await db.execute(
                select(ShelfBook).where(
                    ShelfBook.shelf_id == shelf_id, ShelfBook.work_id == book_id
                )
            )
            if not existing.scalar_one_or_none():
                position = await _shelf_book_count(db, shelf_id)
                db.add(ShelfBook(shelf_id=shelf_id, work_id=book_id, position=position))
                assigned += 1

        # Unassignments
        for shelf_id in req.shelves_to_unassign:
            result = await db.execute(
                select(ShelfBook).where(
                    ShelfBook.shelf_id == shelf_id, ShelfBook.work_id == book_id
                )
            )
            sb = result.scalar_one_or_none()
            if sb:
                await db.delete(sb)
                unassigned += 1

    await db.commit()
    return {"assigned": assigned, "unassigned": unassigned}


@router.get("/{shelf_id}/books", response_model=list)
async def get_shelf_books(
    shelf_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get books for a shelf. Smart shelves evaluate their filter dynamically."""
    stmt = select(Shelf).where(and_(Shelf.id == shelf_id, Shelf.user_id == current_user.id))
    result = await db.execute(stmt)
    shelf = result.scalar_one_or_none()
    if not shelf:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shelf not found")

    if shelf.is_smart and shelf.smart_filter:
        import json
        from app.schemas.book import BookRead

        try:
            rules = json.loads(shelf.smart_filter)
            if isinstance(rules, dict):
                rules = [rules]
        except Exception:
            return []

        book_stmt = select(Book).options(
            joinedload(Book.authors), joinedload(Book.tags), joinedload(Book.series),
            joinedload(Book.files), joinedload(Book.contributors),
        )
        # Determine if any rules need a progress join
        progress_fields = {"status", "rating", "min_rating"}
        needs_progress = any(r.get("field") in progress_fields for r in rules)
        if needs_progress:
            book_stmt = book_stmt.join(
                ReadProgress,
                and_(ReadProgress.edition_id == Book.id, ReadProgress.user_id == current_user.id),
                isouter=False,
            )
        for rule in rules:
            field = rule.get("field", "")
            value = rule.get("value", "")
            if field == "tag":
                book_stmt = book_stmt.where(Book.tags.any(Tag.name.ilike(f"%{value}%")))
            elif field == "author":
                book_stmt = book_stmt.where(Book.authors.any(Author.name.ilike(f"%{value}%")))
            elif field == "series":
                book_stmt = book_stmt.where(Book.series.any(Series.name.ilike(f"%{value}%")))
            elif field == "title":
                book_stmt = book_stmt.where(Book.title.ilike(f"%{value}%"))
            elif field == "language":
                book_stmt = book_stmt.where(Book.language.ilike(f"%{value}%"))
            elif field == "status":
                book_stmt = book_stmt.where(ReadProgress.status == value)
            elif field == "rating":
                try:
                    book_stmt = book_stmt.where(ReadProgress.rating == int(value))
                except (ValueError, TypeError):
                    pass
            elif field == "min_rating":
                try:
                    book_stmt = book_stmt.where(ReadProgress.rating >= int(value))
                except (ValueError, TypeError):
                    pass

        books_result = await db.execute(book_stmt.limit(200))
        books = books_result.unique().scalars().all()
        return [BookRead.model_validate(b) for b in books]
    else:
        # Static shelf — load books via ShelfBook
        from app.schemas.book import BookRead

        book_stmt = (
            select(Book)
            .join(ShelfBook, ShelfBook.work_id == Book.id)
            .where(ShelfBook.shelf_id == shelf_id)
            .options(
                joinedload(Book.authors),
                joinedload(Book.tags),
                joinedload(Book.series),
                joinedload(Book.files),
                joinedload(Book.contributors),
            )
            .order_by(ShelfBook.position)
        )
        result = await db.execute(book_stmt)
        books = result.unique().scalars().all()
        return [BookRead.model_validate(b) for b in books]
