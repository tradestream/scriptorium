from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.database import get_db
from app.models import User
from app.models.annotation import Annotation
from app.models.article import Article
from app.models.edition import Edition
from app.models.marginalium import Marginalium
from app.schemas.book import BookListResponse, BookRead
from app.services.search import search_service

from .auth import get_accessible_library_ids, get_current_user

router = APIRouter(prefix="/search")


class UnifiedSearchResult(BaseModel):
    books: list[dict] = []
    articles: list[dict] = []
    annotations: list[dict] = []
    marginalia: list[dict] = []
    total: int = 0


@router.get("/all", response_model=UnifiedSearchResult)
async def unified_search(
    q: str = Query(..., min_length=1, max_length=200),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Search across books, articles, annotations, and marginalia in one query."""
    pattern = f"%{q}%"
    result = UnifiedSearchResult()

    # Books (FTS5) — scoped to libraries the user can access.
    accessible_ids = await get_accessible_library_ids(db, current_user)
    books, book_total = await search_service.search(
        db, q, limit=limit, offset=0, accessible_library_ids=accessible_ids
    )
    result.books = [
        {
            "id": b.id,
            "type": "book",
            "title": b.title,
            "author": b.authors[0].name if b.authors else None,
            "cover_hash": b.cover_hash,
            "cover_format": b.cover_format,
            "isbn": b.isbn,
        }
        for b in books
    ]

    # Articles
    art_stmt = (
        select(Article)
        .where(Article.user_id == current_user.id)
        .where(Article.title.ilike(pattern) | Article.url.ilike(pattern) | Article.author.ilike(pattern))
        .order_by(Article.saved_at.desc())
        .limit(limit)
    )
    art_rows = (await db.execute(art_stmt)).scalars().all()
    result.articles = [
        {
            "id": a.id,
            "type": "article",
            "title": a.title,
            "author": a.author,
            "domain": a.domain,
            "url": a.url,
            "progress": a.progress,
        }
        for a in art_rows
    ]

    # Annotations
    ann_stmt = (
        select(Annotation)
        .where(Annotation.user_id == current_user.id)
        .where(Annotation.content.ilike(pattern))
        .order_by(Annotation.created_at.desc())
        .limit(limit)
    )
    ann_rows = (await db.execute(ann_stmt)).scalars().all()
    # Bulk-load book titles
    ann_book_ids = list({a.edition_id for a in ann_rows})
    ann_books = {}
    if ann_book_ids:
        bk_result = await db.execute(
            select(Edition).options(joinedload(Edition.work)).where(Edition.id.in_(ann_book_ids))
        )
        for e in bk_result.unique().scalars().all():
            ann_books[e.id] = e.title
    result.annotations = [
        {
            "id": a.id,
            "type": "annotation",
            "content": a.content[:200],
            "book_id": a.edition_id,
            "book_title": ann_books.get(a.edition_id, ""),
            "annotation_type": a.type,
        }
        for a in ann_rows
    ]

    # Marginalia
    mar_stmt = (
        select(Marginalium)
        .where(Marginalium.user_id == current_user.id)
        .where(Marginalium.content.ilike(pattern))
        .order_by(Marginalium.created_at.desc())
        .limit(limit)
    )
    mar_rows = (await db.execute(mar_stmt)).scalars().all()
    mar_book_ids = list({m.edition_id for m in mar_rows})
    mar_books = {}
    if mar_book_ids:
        bk_result = await db.execute(
            select(Edition).options(joinedload(Edition.work)).where(Edition.id.in_(mar_book_ids))
        )
        for e in bk_result.unique().scalars().all():
            mar_books[e.id] = e.title
    result.marginalia = [
        {
            "id": m.id,
            "type": "marginalium",
            "content": m.content[:200],
            "book_id": m.edition_id,
            "book_title": mar_books.get(m.edition_id, ""),
            "kind": m.kind,
        }
        for m in mar_rows
    ]

    result.total = len(result.books) + len(result.articles) + len(result.annotations) + len(result.marginalia)
    return result


@router.get("", response_model=BookListResponse)
async def search_books(
    q: str = Query(..., min_length=1, max_length=200),
    library_id: int | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Full-text search across books using FTS5."""
    accessible_ids = await get_accessible_library_ids(db, current_user)
    books, total = await search_service.search(
        db,
        q,
        limit=limit,
        offset=skip,
        library_id=library_id,
        accessible_library_ids=accessible_ids,
    )

    return BookListResponse(
        items=[BookRead.model_validate(b) for b in books],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("/rebuild-index")
async def rebuild_search_index(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Rebuild the FTS5 search index from scratch (admin only)."""
    from fastapi import HTTPException, status

    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")

    count = await search_service.rebuild_index(db)
    return {"indexed": count}
