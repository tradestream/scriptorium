"""Reading goals — set a target number of books per year and track progress."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.models.progress import ReadingGoal, ReadProgress

from .auth import get_current_user

router = APIRouter(prefix="/goals")


class GoalUpsert(BaseModel):
    target_books: int


class GoalRead(BaseModel):
    year: int
    target_books: int
    books_completed: int
    pct: float          # 0–100

    model_config = {"from_attributes": True}


async def _completed_this_year(db: AsyncSession, user_id: int, year: int) -> int:
    result = await db.scalar(
        select(func.count(ReadProgress.id))
        .where(
            ReadProgress.user_id == user_id,
            ReadProgress.status == "completed",
            extract("year", ReadProgress.completed_at) == year,
        )
    )
    return result or 0


@router.get("/{year}", response_model=GoalRead)
async def get_goal(
    year: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the reading goal and current progress for a given year."""
    result = await db.execute(
        select(ReadingGoal).where(
            ReadingGoal.user_id == current_user.id,
            ReadingGoal.year == year,
        )
    )
    goal = result.scalar_one_or_none()
    target = goal.target_books if goal else 0
    completed = await _completed_this_year(db, current_user.id, year)
    pct = min(100.0, round(completed / target * 100, 1)) if target else 0.0
    return GoalRead(year=year, target_books=target, books_completed=completed, pct=pct)


@router.put("/{year}", response_model=GoalRead)
async def upsert_goal(
    year: int,
    data: GoalUpsert,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create or update the reading goal for a given year."""
    if data.target_books < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="target_books must be ≥ 0")

    result = await db.execute(
        select(ReadingGoal).where(
            ReadingGoal.user_id == current_user.id,
            ReadingGoal.year == year,
        )
    )
    goal = result.scalar_one_or_none()
    if goal:
        goal.target_books = data.target_books
        goal.updated_at = datetime.utcnow()
    else:
        goal = ReadingGoal(
            user_id=current_user.id,
            year=year,
            target_books=data.target_books,
        )
        db.add(goal)
    await db.commit()

    completed = await _completed_this_year(db, current_user.id, year)
    pct = min(100.0, round(completed / data.target_books * 100, 1)) if data.target_books else 0.0
    return GoalRead(year=year, target_books=data.target_books, books_completed=completed, pct=pct)


@router.delete("/{year}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_goal(
    year: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ReadingGoal).where(
            ReadingGoal.user_id == current_user.id,
            ReadingGoal.year == year,
        )
    )
    goal = result.scalar_one_or_none()
    if goal:
        await db.delete(goal)
        await db.commit()
