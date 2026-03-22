from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api.auth import get_current_user
from app.database import get_db
from app.models import User
from app.models.book import Book
from app.models.work import Work
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
                joinedload(Book.work).options(
                    joinedload(Work.authors),
                    joinedload(Work.tags),
                    joinedload(Work.series),
                    joinedload(Work.contributors),
                ),
                joinedload(Book.files),
                joinedload(Book.contributors),
                joinedload(Book.location_ref),
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
                joinedload(Book.work).options(
                    joinedload(Work.authors),
                    joinedload(Work.tags),
                    joinedload(Work.series),
                    joinedload(Work.contributors),
                ),
                joinedload(Book.files),
                joinedload(Book.contributors),
                joinedload(Book.location_ref),
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
            joinedload(Book.work).options(
                joinedload(Work.authors),
                joinedload(Work.tags),
                joinedload(Work.series),
                joinedload(Work.contributors),
            ),
            joinedload(Book.files),
            joinedload(Book.contributors),
            joinedload(Book.location_ref),
        )
        .where(Book.id == data.primary_id)
    )
    primary = primary_result.unique().scalar_one_or_none()
    if not primary:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Primary book not found")

    primary_work_id = primary.work_id

    for src_id in data.source_ids:
        if src_id == data.primary_id:
            continue

        # Load source edition to get its work_id
        src_result = await db.execute(select(Book).where(Book.id == src_id))
        src_edition = src_result.scalar_one_or_none()
        if not src_edition:
            continue
        src_work_id = src_edition.work_id

        # Move work-level data if different works
        if src_work_id and primary_work_id and src_work_id != primary_work_id:
            # Shelf assignments
            await db.execute(
                text("UPDATE OR IGNORE shelf_books SET work_id = :primary WHERE work_id = :src"),
                {"primary": primary_work_id, "src": src_work_id},
            )
            await db.execute(text("DELETE FROM shelf_books WHERE work_id = :src"), {"src": src_work_id})
            # Collection assignments
            await db.execute(
                text("UPDATE OR IGNORE collection_books SET work_id = :primary WHERE work_id = :src"),
                {"primary": primary_work_id, "src": src_work_id},
            )
            await db.execute(text("DELETE FROM collection_books WHERE work_id = :src"), {"src": src_work_id})
            # Read sessions
            await db.execute(
                text("UPDATE OR IGNORE read_sessions SET work_id = :primary WHERE work_id = :src"),
                {"primary": primary_work_id, "src": src_work_id},
            )
            await db.execute(text("DELETE FROM read_sessions WHERE work_id = :src"), {"src": src_work_id})

        # Move files (skip if same format already exists on primary)
        await db.execute(
            text(
                "UPDATE OR IGNORE edition_files SET edition_id = :primary WHERE edition_id = :src"
            ),
            {"primary": data.primary_id, "src": src_id},
        )
        # Delete any remaining files that couldn't be moved (duplicate hash/path)
        await db.execute(
            text("DELETE FROM edition_files WHERE edition_id = :src"),
            {"src": src_id},
        )

        # Move annotations
        await db.execute(
            text("UPDATE OR IGNORE annotations SET edition_id = :primary WHERE edition_id = :src"),
            {"primary": data.primary_id, "src": src_id},
        )
        # Move marginalia
        await db.execute(
            text("UPDATE OR IGNORE marginalia SET edition_id = :primary WHERE edition_id = :src"),
            {"primary": data.primary_id, "src": src_id},
        )
        # Move read progress — skip if primary already has one for the same user
        await db.execute(
            text(
                "UPDATE OR IGNORE read_progress SET edition_id = :primary WHERE edition_id = :src "
                "AND NOT EXISTS (SELECT 1 FROM read_progress rp2 WHERE rp2.edition_id = :primary AND rp2.user_id = read_progress.user_id)"
            ),
            {"primary": data.primary_id, "src": src_id},
        )
        # Move user editions — skip duplicates
        await db.execute(
            text(
                "UPDATE OR IGNORE user_editions SET edition_id = :primary WHERE edition_id = :src"
            ),
            {"primary": data.primary_id, "src": src_id},
        )
        # Move edition contributors
        await db.execute(
            text(
                "UPDATE OR IGNORE edition_contributors SET edition_id = :primary WHERE edition_id = :src"
            ),
            {"primary": data.primary_id, "src": src_id},
        )
        # Move Kobo state
        await db.execute(
            text(
                "UPDATE OR IGNORE kobo_book_states SET edition_id = :primary WHERE edition_id = :src"
            ),
            {"primary": data.primary_id, "src": src_id},
        )
        # Move Kobo bookmarks
        await db.execute(
            text(
                "UPDATE OR IGNORE kobo_bookmarks SET edition_id = :primary WHERE edition_id = :src"
            ),
            {"primary": data.primary_id, "src": src_id},
        )
        # Move Kobo synced books
        await db.execute(
            text(
                "UPDATE OR IGNORE kobo_synced_books SET edition_id = :primary WHERE edition_id = :src"
            ),
            {"primary": data.primary_id, "src": src_id},
        )

        # Clean up any remaining references that couldn't be moved (duplicates)
        for tbl in ("annotations", "marginalia", "read_progress", "user_editions",
                     "edition_contributors", "kobo_book_states", "kobo_bookmarks", "kobo_synced_books"):
            await db.execute(text(f"DELETE FROM {tbl} WHERE edition_id = :src"), {"src": src_id})

        # Delete source edition
        await db.execute(
            text("DELETE FROM editions WHERE id = :src"),
            {"src": src_id},
        )

        # Delete orphaned work if it has no more editions
        if src_work_id and src_work_id != primary_work_id:
            orphan_check = await db.execute(
                text("SELECT COUNT(*) FROM editions WHERE work_id = :wid"),
                {"wid": src_work_id},
            )
            if orphan_check.scalar() == 0:
                # Clean up work associations
                for assoc in ("work_authors", "work_tags", "work_series", "work_contributors"):
                    await db.execute(text(f"DELETE FROM {assoc} WHERE work_id = :wid"), {"wid": src_work_id})
                await db.execute(text("DELETE FROM works WHERE id = :wid"), {"wid": src_work_id})

    await db.commit()

    # Re-fetch primary with all relationships
    fresh_result = await db.execute(
        select(Book)
        .options(
            joinedload(Book.work).options(
                joinedload(Work.authors),
                joinedload(Work.tags),
                joinedload(Work.series),
                joinedload(Work.contributors),
            ),
            joinedload(Book.files),
            joinedload(Book.contributors),
            joinedload(Book.location_ref),
        )
        .where(Book.id == data.primary_id)
    )
    primary = fresh_result.unique().scalar_one()

    # Re-index FTS
    from app.services.search import search_service
    await search_service.index_book(db, primary, [a.name for a in primary.authors])
    await db.commit()

    return BookRead.model_validate(primary)
