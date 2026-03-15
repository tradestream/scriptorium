from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api.auth import get_current_user
from app.database import get_db
from app.models import User
from app.models.book import Book
from app.schemas.book import BookRead

router = APIRouter(prefix="/duplicates", tags=["duplicates"])


@router.get("/isbn", response_model=list[list[BookRead]])
async def find_isbn_duplicates(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Find books sharing the same ISBN (non-null). Returns groups of duplicates."""
    # Find ISBNs that appear more than once
    dup_result = await db.execute(
        select(Book.isbn)
        .where(Book.isbn.isnot(None))
        .group_by(Book.isbn)
        .having(func.count(Book.id) > 1)
    )
    dup_isbns = [row[0] for row in dup_result.all()]

    if not dup_isbns:
        return []

    groups = []
    for isbn in dup_isbns:
        books_result = await db.execute(
            select(Book)
            .options(
                joinedload(Book.authors),
                joinedload(Book.tags),
                joinedload(Book.series),
                joinedload(Book.files),
                joinedload(Book.contributors),
            )
            .where(Book.isbn == isbn)
            .order_by(Book.created_at)
        )
        books = books_result.unique().scalars().all()
        groups.append([BookRead.model_validate(b) for b in books])

    return groups


@router.get("/title-author", response_model=list[list[BookRead]])
async def find_title_author_duplicates(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Find books with the exact same normalised title that share an author."""
    from sqlalchemy import and_
    from app.models.book import book_authors

    # Find normalised titles appearing more than once
    dup_result = await db.execute(
        select(func.lower(func.trim(Book.title)).label("norm_title"))
        .group_by(func.lower(func.trim(Book.title)))
        .having(func.count(Book.id) > 1)
    )
    dup_titles = [row[0] for row in dup_result.all()]

    if not dup_titles:
        return []

    groups = []
    for norm_title in dup_titles:
        books_result = await db.execute(
            select(Book)
            .options(
                joinedload(Book.authors),
                joinedload(Book.tags),
                joinedload(Book.series),
                joinedload(Book.files),
                joinedload(Book.contributors),
            )
            .where(func.lower(func.trim(Book.title)) == norm_title)
            .order_by(Book.created_at)
        )
        books = books_result.unique().scalars().all()
        if len(books) > 1:
            # Only report as duplicates if they share at least one author
            author_sets = [set(a.id for a in b.authors) for b in books]
            has_shared_author = any(
                author_sets[i] & author_sets[j]
                for i in range(len(author_sets))
                for j in range(i + 1, len(author_sets))
            )
            if has_shared_author or all(len(s) == 0 for s in author_sets):
                groups.append([BookRead.model_validate(b) for b in books])

    return groups


from pydantic import BaseModel
from sqlalchemy import text


class ConsolidateRequest(BaseModel):
    primary_id: int
    source_ids: list[int]


@router.post("/consolidate", response_model=BookRead)
async def consolidate_duplicates(
    data: ConsolidateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Merge source books into primary: moves all user data, deletes sources.
    Admin only — destructive operation."""
    from fastapi import HTTPException, status

    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")

    # Load primary book
    primary_result = await db.execute(
        select(Book)
        .options(
            joinedload(Book.authors),
            joinedload(Book.tags),
            joinedload(Book.series),
            joinedload(Book.files),
            joinedload(Book.contributors),
        )
        .where(Book.id == data.primary_id)
    )
    primary = primary_result.unique().scalar_one_or_none()
    if not primary:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Primary book not found")

    for src_id in data.source_ids:
        if src_id == data.primary_id:
            continue

        # Move annotations
        await db.execute(
            text("UPDATE annotations SET book_id = :primary WHERE book_id = :src"),
            {"primary": data.primary_id, "src": src_id},
        )
        # Move read sessions
        await db.execute(
            text("UPDATE read_sessions SET book_id = :primary WHERE book_id = :src"),
            {"primary": data.primary_id, "src": src_id},
        )
        # Move read progress — skip if primary already has one
        await db.execute(
            text(
                "UPDATE read_progress SET book_id = :primary WHERE book_id = :src "
                "AND NOT EXISTS (SELECT 1 FROM read_progress WHERE book_id = :primary AND user_id = read_progress.user_id)"
            ),
            {"primary": data.primary_id, "src": src_id},
        )
        # Shelf assignments — skip duplicates
        await db.execute(
            text(
                "UPDATE OR IGNORE shelf_books SET book_id = :primary WHERE book_id = :src"
            ),
            {"primary": data.primary_id, "src": src_id},
        )
        # Collection assignments — skip duplicates
        await db.execute(
            text(
                "UPDATE OR IGNORE collection_books SET book_id = :primary WHERE book_id = :src"
            ),
            {"primary": data.primary_id, "src": src_id},
        )

        # Delete source book (cascades files, authors, tags, series, FTS via trigger)
        await db.execute(
            text("DELETE FROM books WHERE id = :src"),
            {"src": src_id},
        )

    await db.commit()

    # Re-fetch primary with all relationships
    fresh_result = await db.execute(
        select(Book)
        .options(
            joinedload(Book.authors),
            joinedload(Book.tags),
            joinedload(Book.series),
            joinedload(Book.files),
            joinedload(Book.contributors),
        )
        .where(Book.id == data.primary_id)
    )
    primary = fresh_result.unique().scalar_one()

    # Re-index FTS
    from app.services.search import search_service
    await search_service.index_book(db, primary, [a.name for a in primary.authors])
    await db.commit()

    return BookRead.model_validate(primary)
