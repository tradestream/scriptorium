from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.schemas.book import BookListResponse, BookRead
from app.services.search import search_service

from .auth import get_current_user

router = APIRouter(prefix="/search")


@router.get("", response_model=BookListResponse)
async def search_books(
    q: str = Query(..., min_length=1, max_length=200),
    library_id: int | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Full-text search across books using FTS5."""
    books, total = await search_service.search(
        db, q, limit=limit, offset=skip, library_id=library_id
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
