from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.database import get_db
from app.models import User
from app.models.read_session import ReadSession
from app.schemas.read_session import ReadSessionCreate, ReadSessionRead, ReadSessionUpdate

router = APIRouter(prefix="/read-sessions", tags=["read-sessions"])


@router.get("", response_model=list[ReadSessionRead])
async def list_read_sessions(
    book_id: int | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List read sessions, optionally filtered to one book."""
    stmt = select(ReadSession).where(ReadSession.user_id == current_user.id)
    if book_id is not None:
        stmt = stmt.where(ReadSession.book_id == book_id)
    stmt = stmt.order_by(ReadSession.started_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("", response_model=ReadSessionRead, status_code=status.HTTP_201_CREATED)
async def create_read_session(
    data: ReadSessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Log a read session (new or re-read)."""
    session = ReadSession(
        user_id=current_user.id,
        book_id=data.book_id,
        started_at=data.started_at,
        finished_at=data.finished_at,
        rating=data.rating,
        notes=data.notes,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


@router.put("/{session_id}", response_model=ReadSessionRead)
async def update_read_session(
    session_id: int,
    data: ReadSessionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ReadSession).where(
            and_(ReadSession.id == session_id, ReadSession.user_id == current_user.id)
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if data.started_at is not None:
        session.started_at = data.started_at
    if data.finished_at is not None:
        session.finished_at = data.finished_at
    if data.rating is not None:
        session.rating = data.rating
    if data.notes is not None:
        session.notes = data.notes
    await db.commit()
    await db.refresh(session)
    return session


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_read_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ReadSession).where(
            and_(ReadSession.id == session_id, ReadSession.user_id == current_user.id)
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    await db.delete(session)
    await db.commit()
