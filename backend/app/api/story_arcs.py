"""Story Arcs API — browse and manage comic story arcs."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api.auth import get_current_user
from app.database import get_db
from app.models import User
from app.models.comic import StoryArc, StoryArcEntry

router = APIRouter(prefix="/story-arcs", tags=["story-arcs"])


class StoryArcRead(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    entry_count: int = 0

    class Config:
        from_attributes = True


class StoryArcEntryRead(BaseModel):
    work_id: int
    title: str
    sequence_number: Optional[float] = None
    authors: list[str] = []


class StoryArcDetail(StoryArcRead):
    entries: list[StoryArcEntryRead] = []


@router.get("", response_model=list[StoryArcRead])
async def list_story_arcs(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(
            StoryArc.id,
            StoryArc.name,
            StoryArc.description,
            func.count(StoryArcEntry.id).label("entry_count"),
        )
        .outerjoin(StoryArcEntry, StoryArcEntry.story_arc_id == StoryArc.id)
        .group_by(StoryArc.id)
        .order_by(StoryArc.name)
    )
    return [
        StoryArcRead(id=r[0], name=r[1], description=r[2], entry_count=r[3])
        for r in result.all()
    ]


@router.get("/{arc_id}", response_model=StoryArcDetail)
async def get_story_arc(
    arc_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    arc = (await db.execute(
        select(StoryArc).where(StoryArc.id == arc_id)
    )).scalar_one_or_none()
    if not arc:
        raise HTTPException(status_code=404, detail="Story arc not found")

    from app.models.work import Work
    entries_result = await db.execute(
        select(StoryArcEntry, Work)
        .join(Work, Work.id == StoryArcEntry.work_id)
        .where(StoryArcEntry.story_arc_id == arc_id)
        .options(joinedload(Work.authors))
        .order_by(StoryArcEntry.sequence_number.nulls_last(), Work.title)
    )
    entries = []
    for entry, work in entries_result.unique().all():
        entries.append(StoryArcEntryRead(
            work_id=work.id,
            title=work.title,
            sequence_number=entry.sequence_number,
            authors=[a.name for a in work.authors],
        ))

    count = await db.scalar(
        select(func.count()).where(StoryArcEntry.story_arc_id == arc_id)
    )

    return StoryArcDetail(
        id=arc.id, name=arc.name, description=arc.description,
        entry_count=count or 0, entries=entries,
    )
