"""Ordered reading lists.

Distinct from ``shelves`` (flat user-curated bag) and ``collections``
(flat or smart-filtered grouping). A reading list is an *ordered*
sequence: read entry 1, then 2, then 3, with explicit next/previous
navigation. Borrowed from Kavita / Komga where reading lists are a
separate first-class entity.

Endpoints:

  GET    /reading-lists                       — index (own lists)
  POST   /reading-lists                       — create
  GET    /reading-lists/{id}                  — detail with ordered entries
  PUT    /reading-lists/{id}                  — update meta
  DELETE /reading-lists/{id}
  POST   /reading-lists/{id}/entries          — add an entry
  PUT    /reading-lists/{id}/entries          — bulk reorder (full list of ids)
  DELETE /reading-lists/{id}/entries/{entry_id}
  GET    /reading-lists/{id}/next?after=ed_id — next edition after one in the list
  GET    /reading-lists/{id}/previous?before=ed_id

Position is a sparse integer (steps of 10) so a single-row insert /
move can land between two rows without rewriting the whole list. Bulk
reorder renumbers from scratch.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.auth import assert_edition_access, get_current_user
from app.database import get_db
from app.models import User
from app.models.edition import Edition
from app.models.reading_list import ReadingList, ReadingListEntry
from app.schemas.book import BookRead
from app.schemas.reading_list import (
    ReadingListCreate,
    ReadingListDetail,
    ReadingListEntryAdd,
    ReadingListEntryRead,
    ReadingListEntryReorder,
    ReadingListRead,
    ReadingListUpdate,
)

router = APIRouter(prefix="/reading-lists", tags=["reading-lists"])

POSITION_STEP = 10


async def _get_or_404(
    list_id: int, user_id: int, db: AsyncSession
) -> ReadingList:
    rl = (
        await db.execute(
            select(ReadingList).where(
                ReadingList.id == list_id, ReadingList.user_id == user_id
            )
        )
    ).scalar_one_or_none()
    if rl is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Reading list not found"
        )
    return rl


async def _entry_count(list_id: int, db: AsyncSession) -> int:
    return await db.scalar(
        select(func.count(ReadingListEntry.id)).where(
            ReadingListEntry.reading_list_id == list_id
        )
    ) or 0


# ── Reading list CRUD ────────────────────────────────────────────────


@router.get("", response_model=list[ReadingListRead])
async def list_reading_lists(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (
        await db.execute(
            select(ReadingList)
            .where(ReadingList.user_id == current_user.id)
            .order_by(ReadingList.is_pinned.desc(), ReadingList.updated_at.desc())
        )
    ).scalars().all()
    counts = {
        rid: cnt
        for rid, cnt in (
            await db.execute(
                select(
                    ReadingListEntry.reading_list_id,
                    func.count(ReadingListEntry.id),
                )
                .where(
                    ReadingListEntry.reading_list_id.in_([r.id for r in rows] or [-1])
                )
                .group_by(ReadingListEntry.reading_list_id)
            )
        ).all()
    }
    out: list[ReadingListRead] = []
    for r in rows:
        item = ReadingListRead.model_validate(r)
        item.entry_count = counts.get(r.id, 0)
        out.append(item)
    return out


@router.post("", response_model=ReadingListRead, status_code=status.HTTP_201_CREATED)
async def create_reading_list(
    data: ReadingListCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rl = ReadingList(
        user_id=current_user.id,
        name=data.name.strip(),
        description=data.description,
        cover_work_id=data.cover_work_id,
        is_pinned=data.is_pinned,
        sync_to_kobo=data.sync_to_kobo,
    )
    db.add(rl)
    await db.commit()
    await db.refresh(rl)
    item = ReadingListRead.model_validate(rl)
    item.entry_count = 0
    return item


@router.get("/{list_id}", response_model=ReadingListDetail)
async def get_reading_list(
    list_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rl = await _get_or_404(list_id, current_user.id, db)

    # Pull entries with their editions in one round trip.
    from app.api.books import _edition_options

    entries = (
        await db.execute(
            select(ReadingListEntry)
            .where(ReadingListEntry.reading_list_id == list_id)
            .order_by(ReadingListEntry.position)
            .options(
                selectinload(ReadingListEntry.reading_list),
            )
        )
    ).scalars().all()

    edition_ids = [e.edition_id for e in entries]
    editions_by_id: dict[int, Edition] = {}
    if edition_ids:
        eds = (
            await db.execute(
                select(Edition).options(*_edition_options()).where(Edition.id.in_(edition_ids))
            )
        ).unique().scalars().all()
        editions_by_id = {e.id: e for e in eds}

    detail = ReadingListDetail.model_validate(rl)
    detail.entries = [
        ReadingListEntryRead(
            id=e.id,
            position=e.position,
            notes=e.notes,
            book=BookRead.model_validate(editions_by_id[e.edition_id]),
        )
        for e in entries
        if e.edition_id in editions_by_id
    ]
    detail.entry_count = len(detail.entries)
    return detail


@router.put("/{list_id}", response_model=ReadingListRead)
async def update_reading_list(
    list_id: int,
    data: ReadingListUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rl = await _get_or_404(list_id, current_user.id, db)
    if data.name is not None:
        rl.name = data.name.strip()
    if data.description is not None:
        rl.description = data.description
    if data.cover_work_id is not None:
        rl.cover_work_id = data.cover_work_id
    if data.is_pinned is not None:
        rl.is_pinned = data.is_pinned
    if data.sync_to_kobo is not None:
        rl.sync_to_kobo = data.sync_to_kobo
    await db.commit()
    await db.refresh(rl)
    item = ReadingListRead.model_validate(rl)
    item.entry_count = await _entry_count(list_id, db)
    return item


@router.delete("/{list_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_reading_list(
    list_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rl = await _get_or_404(list_id, current_user.id, db)
    await db.delete(rl)
    await db.commit()


# ── Entries ──────────────────────────────────────────────────────────


@router.post(
    "/{list_id}/entries",
    response_model=ReadingListEntryRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_entry(
    list_id: int,
    data: ReadingListEntryAdd,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rl = await _get_or_404(list_id, current_user.id, db)
    edition = await assert_edition_access(db, current_user, data.book_id)

    # Compute the position. If the caller specified one, slot it in
    # exactly there; otherwise append after the current last entry.
    if data.position is None:
        max_pos = await db.scalar(
            select(func.max(ReadingListEntry.position)).where(
                ReadingListEntry.reading_list_id == list_id
            )
        )
        position = (max_pos or 0) + POSITION_STEP
    else:
        position = data.position

    entry = ReadingListEntry(
        reading_list_id=list_id,
        edition_id=edition.id,
        position=position,
        notes=data.notes,
    )
    db.add(entry)
    rl.updated_at = func.now()  # type: ignore[assignment]
    await db.commit()
    await db.refresh(entry)

    from app.api.books import _edition_options

    full_edition = (
        await db.execute(
            select(Edition).options(*_edition_options()).where(Edition.id == edition.id)
        )
    ).unique().scalar_one()
    return ReadingListEntryRead(
        id=entry.id,
        position=entry.position,
        notes=entry.notes,
        book=BookRead.model_validate(full_edition),
    )


@router.put("/{list_id}/entries", response_model=list[ReadingListEntryRead])
async def reorder_entries(
    list_id: int,
    data: ReadingListEntryReorder,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Renumber every entry's ``position`` according to the order of
    ``entry_ids``. Any entry not listed is left in place at the end —
    callers should send the full ordered list to be safe.
    """
    rl = await _get_or_404(list_id, current_user.id, db)

    entries = (
        await db.execute(
            select(ReadingListEntry).where(
                ReadingListEntry.reading_list_id == list_id
            )
        )
    ).scalars().all()
    by_id = {e.id: e for e in entries}

    seen: set[int] = set()
    pos = POSITION_STEP
    for eid in data.entry_ids:
        e = by_id.get(eid)
        if e is None:
            continue
        e.position = pos
        seen.add(eid)
        pos += POSITION_STEP
    # Leftover entries (caller didn't include them) keep relative order
    # but go after everything in the explicit list.
    leftover = sorted(
        (e for e in entries if e.id not in seen), key=lambda e: e.position
    )
    for e in leftover:
        e.position = pos
        pos += POSITION_STEP

    rl.updated_at = func.now()  # type: ignore[assignment]
    await db.commit()
    return await _detail_entries(list_id, db)


@router.delete(
    "/{list_id}/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def remove_entry(
    list_id: int,
    entry_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rl = await _get_or_404(list_id, current_user.id, db)
    entry = (
        await db.execute(
            select(ReadingListEntry).where(
                ReadingListEntry.id == entry_id,
                ReadingListEntry.reading_list_id == list_id,
            )
        )
    ).scalar_one_or_none()
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found"
        )
    await db.delete(entry)
    rl.updated_at = func.now()  # type: ignore[assignment]
    await db.commit()


async def _detail_entries(
    list_id: int, db: AsyncSession
) -> list[ReadingListEntryRead]:
    """Helper used by reorder + future bulk endpoints."""
    from app.api.books import _edition_options

    entries = (
        await db.execute(
            select(ReadingListEntry)
            .where(ReadingListEntry.reading_list_id == list_id)
            .order_by(ReadingListEntry.position)
        )
    ).scalars().all()
    edition_ids = [e.edition_id for e in entries]
    editions_by_id: dict[int, Edition] = {}
    if edition_ids:
        eds = (
            await db.execute(
                select(Edition).options(*_edition_options()).where(Edition.id.in_(edition_ids))
            )
        ).unique().scalars().all()
        editions_by_id = {e.id: e for e in eds}
    return [
        ReadingListEntryRead(
            id=e.id,
            position=e.position,
            notes=e.notes,
            book=BookRead.model_validate(editions_by_id[e.edition_id]),
        )
        for e in entries
        if e.edition_id in editions_by_id
    ]


# ── Navigation: next / previous within a list ────────────────────────


@router.get("/{list_id}/next", response_model=Optional[ReadingListEntryRead])
async def next_in_list(
    list_id: int,
    after: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the next entry after the entry whose ``edition_id`` is
    ``after``. ``null`` (HTTP 200 with body ``null``) if there is no
    next entry, or if ``after`` is not in the list.
    """
    await _get_or_404(list_id, current_user.id, db)
    return await _adjacent(list_id, after, direction="next", db=db)


@router.get("/{list_id}/previous", response_model=Optional[ReadingListEntryRead])
async def previous_in_list(
    list_id: int,
    before: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_or_404(list_id, current_user.id, db)
    return await _adjacent(list_id, before, direction="previous", db=db)


async def _adjacent(
    list_id: int,
    edition_id: int,
    *,
    direction: str,
    db: AsyncSession,
) -> Optional[ReadingListEntryRead]:
    pivot = (
        await db.execute(
            select(ReadingListEntry).where(
                ReadingListEntry.reading_list_id == list_id,
                ReadingListEntry.edition_id == edition_id,
            )
        )
    ).scalar_one_or_none()
    if pivot is None:
        return None
    if direction == "next":
        stmt = (
            select(ReadingListEntry)
            .where(
                ReadingListEntry.reading_list_id == list_id,
                ReadingListEntry.position > pivot.position,
            )
            .order_by(ReadingListEntry.position)
            .limit(1)
        )
    else:
        stmt = (
            select(ReadingListEntry)
            .where(
                ReadingListEntry.reading_list_id == list_id,
                ReadingListEntry.position < pivot.position,
            )
            .order_by(ReadingListEntry.position.desc())
            .limit(1)
        )
    neighbour = (await db.execute(stmt)).scalar_one_or_none()
    if neighbour is None:
        return None

    from app.api.books import _edition_options

    edition = (
        await db.execute(
            select(Edition).options(*_edition_options()).where(Edition.id == neighbour.edition_id)
        )
    ).unique().scalar_one_or_none()
    if edition is None:
        return None
    return ReadingListEntryRead(
        id=neighbour.id,
        position=neighbour.position,
        notes=neighbour.notes,
        book=BookRead.model_validate(edition),
    )
