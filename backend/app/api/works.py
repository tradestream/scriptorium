"""Works API — CRUD for abstract creative works."""

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import (
    Author,
    Edition,
    Library,
    Series,
    Tag,
    User,
    Work,
    WorkContributor,
)
from app.schemas.edition import EditionRead
from app.schemas.work import WorkCreate, WorkListResponse, WorkRead, WorkUpdate

from .auth import get_accessible_library_ids, get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/works")


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_work_or_404(work_id: int, db: AsyncSession) -> Work:
    result = await db.execute(
        select(Work)
        .where(Work.id == work_id)
        .options(
            selectinload(Work.authors),
            selectinload(Work.tags),
            selectinload(Work.series),
            selectinload(Work.contributors),
            selectinload(Work.editions),
        )
    )
    work = result.scalar_one_or_none()
    if work is None:
        raise HTTPException(status_code=404, detail="Work not found")
    return work


async def _resolve_names(db: AsyncSession, model, names: list[str]) -> list:
    """Get-or-create lookup entities (Author / Tag / Series) by name."""
    entities = []
    for name in names:
        name = name.strip()
        if not name:
            continue
        result = await db.execute(select(model).where(model.name == name))
        entity = result.scalar_one_or_none()
        if entity is None:
            entity = model(name=name)
            db.add(entity)
            await db.flush()
        entities.append(entity)
    return entities


async def _apply_work_update(work: Work, body: WorkUpdate, db: AsyncSession) -> None:
    for field in ("title", "subtitle", "description", "language", "esoteric_enabled"):
        val = getattr(body, field, None)
        if val is not None:
            setattr(work, field, val)

    if body.locked_fields is not None:
        import json
        work.locked_fields = json.dumps(body.locked_fields)

    if body.author_names is not None:
        work.authors = await _resolve_names(db, Author, body.author_names)
    if body.tag_names is not None:
        work.tags = await _resolve_names(db, Tag, body.tag_names)
    if body.series_names is not None:
        work.series = await _resolve_names(db, Series, body.series_names)

    for role, attr in [("editor", "editor_names"), ("illustrator", "illustrator_names"), ("colorist", "colorist_names")]:
        names = getattr(body, attr, None)
        if names is not None:
            # Replace all contributors for this role
            work.contributors = [c for c in work.contributors if c.role != role]
            for name in names:
                if name.strip():
                    work.contributors.append(WorkContributor(work_id=work.id, name=name.strip(), role=role))


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=WorkListResponse)
async def list_works(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=5000),
    library_id: Optional[int] = None,
    include_hidden: bool = False,
    search: Optional[str] = None,
    author_id: Optional[int] = None,
    tag_id: Optional[int] = None,
    sort_by: str = Query("date_added", pattern="^(date_added|title)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List works with pagination and filtering.

    Works are filtered by the libraries the current user can access.
    A work appears in the list if it has at least one edition in an
    accessible library.
    """
    accessible_ids = await get_accessible_library_ids(db, current_user)

    # Base: works that have an edition in an accessible library
    stmt = select(Work).join(Work.editions)

    if accessible_ids is not None:
        stmt = stmt.where(Edition.library_id.in_(accessible_ids))

    if library_id:
        stmt = stmt.where(Edition.library_id == library_id)
    elif not include_hidden:
        hidden_lib_ids = select(Library.id).where(Library.is_hidden == True)
        stmt = stmt.where(Edition.library_id.notin_(hidden_lib_ids))

    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(
            or_(Work.title.ilike(pattern), Work.description.ilike(pattern))
        )
    if author_id:
        stmt = stmt.where(Work.authors.any(id=author_id))
    if tag_id:
        stmt = stmt.where(Work.tags.any(id=tag_id))

    stmt = stmt.distinct()

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.scalar(count_stmt)) or 0

    if sort_by == "title":
        stmt = stmt.order_by(Work.title)
    else:
        stmt = stmt.order_by(Work.created_at.desc())

    stmt = stmt.offset(skip).limit(limit).options(
        selectinload(Work.authors),
        selectinload(Work.tags),
        selectinload(Work.series),
        selectinload(Work.contributors),
        selectinload(Work.editions),
    )
    result = await db.execute(stmt)
    works = result.scalars().unique().all()

    items = []
    for w in works:
        wr = WorkRead.model_validate(w)
        wr.edition_count = len(w.editions)
        items.append(wr)

    return WorkListResponse(items=items, total=total, skip=skip, limit=limit)


@router.get("/{work_id}", response_model=WorkRead)
async def get_work(
    work_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    work = await _get_work_or_404(work_id, db)
    wr = WorkRead.model_validate(work)
    wr.edition_count = len(work.editions)
    return wr


@router.post("", response_model=WorkRead, status_code=status.HTTP_201_CREATED)
async def create_work(
    body: WorkCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    work = Work(
        uuid=str(uuid.uuid4()),
        title=body.title,
        subtitle=body.subtitle,
        description=body.description,
        language=body.language,
        esoteric_enabled=body.esoteric_enabled,
    )
    db.add(work)
    await db.flush()

    work.authors = await _resolve_names(db, Author, body.author_names)
    work.tags = await _resolve_names(db, Tag, body.tag_names)

    for role, attr in [("editor", "editor_names"), ("illustrator", "illustrator_names"), ("colorist", "colorist_names")]:
        for name in getattr(body, attr, []):
            if name.strip():
                db.add(WorkContributor(work_id=work.id, name=name.strip(), role=role))

    await db.commit()
    await db.refresh(work)
    work = await _get_work_or_404(work.id, db)
    wr = WorkRead.model_validate(work)
    wr.edition_count = len(work.editions)
    return wr


@router.put("/{work_id}", response_model=WorkRead)
async def update_work(
    work_id: int,
    body: WorkUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    work = await _get_work_or_404(work_id, db)
    await _apply_work_update(work, body, db)
    await db.commit()
    work = await _get_work_or_404(work_id, db)
    wr = WorkRead.model_validate(work)
    wr.edition_count = len(work.editions)
    return wr


@router.delete("/{work_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_work(
    work_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin only")
    work = await _get_work_or_404(work_id, db)
    await db.delete(work)
    await db.commit()


@router.get("/{work_id}/editions", response_model=list[EditionRead])
async def list_work_editions(
    work_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all editions for a work that the user can access."""
    accessible_ids = await get_accessible_library_ids(db, current_user)

    stmt = (
        select(Edition)
        .where(Edition.work_id == work_id)
        .options(selectinload(Edition.files), selectinload(Edition.contributors))
    )
    if accessible_ids is not None:
        stmt = stmt.where(Edition.library_id.in_(accessible_ids))

    result = await db.execute(stmt)
    editions = result.scalars().all()
    return [EditionRead.model_validate(e) for e in editions]
