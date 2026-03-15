"""Marginalia — Scriptorium-native scholarly notes on book passages."""

import json
import re
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api.auth import get_current_user
from app.database import get_db
from app.models import Book, User
from app.models.marginalium import Marginalium
from app.schemas.marginalium import (
    MarginaliumCreate,
    MarginaliumRead,
    MarginaliumUpdate,
    MarginaliumWithBook,
)

router = APIRouter(prefix="/marginalia", tags=["marginalia"])


def _serialize_list(v: list[str] | None) -> str | None:
    return json.dumps(v) if v is not None else None


@router.get("", response_model=list[MarginaliumRead])
async def list_marginalia(
    book_id: int = Query(..., description="Filter by book"),
    kind: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(Marginalium).where(
        Marginalium.user_id == current_user.id,
        Marginalium.book_id == book_id,
    )
    if kind:
        stmt = stmt.where(Marginalium.kind == kind)
    stmt = stmt.order_by(Marginalium.created_at)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/mine", response_model=list[MarginaliumWithBook])
async def list_my_marginalia(
    kind: str | None = Query(default=None),
    q: str | None = Query(default=None, description="Search content"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(Marginalium).where(Marginalium.user_id == current_user.id)
    if kind:
        stmt = stmt.where(Marginalium.kind == kind)
    if q:
        stmt = stmt.where(Marginalium.content.ilike(f"%{q}%"))
    stmt = stmt.order_by(Marginalium.created_at.desc())
    result = await db.execute(stmt)
    items = result.scalars().all()

    book_ids = list({m.book_id for m in items})
    books_map: dict[int, Book] = {}
    if book_ids:
        bk_result = await db.execute(
            select(Book).where(Book.id.in_(book_ids)).options(joinedload(Book.authors))
        )
        for b in bk_result.unique().scalars().all():
            books_map[b.id] = b

    out = []
    for m in items:
        bk = books_map.get(m.book_id)
        out.append(
            MarginaliumWithBook.model_validate(
                {
                    "id": m.id,
                    "user_id": m.user_id,
                    "book_id": m.book_id,
                    "file_id": m.file_id,
                    "kind": m.kind,
                    "reading_level": m.reading_level,
                    "content": m.content,
                    "location": m.location,
                    "chapter": m.chapter,
                    "related_refs": m.related_refs,
                    "tags": m.tags,
                    "commentator": m.commentator,
                    "source": m.source,
                    "created_at": m.created_at,
                    "updated_at": m.updated_at,
                    "book_title": bk.title if bk else None,
                    "book_author": bk.authors[0].name if bk and bk.authors else None,
                }
            )
        )
    return out


@router.post("", response_model=MarginaliumRead, status_code=status.HTTP_201_CREATED)
async def create_marginalium(
    data: MarginaliumCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    m = Marginalium(
        user_id=current_user.id,
        book_id=data.book_id,
        file_id=data.file_id,
        kind=data.kind,
        reading_level=data.reading_level,
        content=data.content,
        location=data.location,
        chapter=data.chapter,
        related_refs=_serialize_list(data.related_refs),
        tags=_serialize_list(data.tags),
        commentator=data.commentator,
        source=data.source,
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return m


@router.put("/{marginalium_id}", response_model=MarginaliumRead)
async def update_marginalium(
    marginalium_id: int,
    data: MarginaliumUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Marginalium).where(
            and_(Marginalium.id == marginalium_id, Marginalium.user_id == current_user.id)
        )
    )
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Marginalium not found")
    if data.kind is not None:
        m.kind = data.kind
    if data.reading_level is not None:
        m.reading_level = data.reading_level
    if data.content is not None:
        m.content = data.content
    if data.location is not None:
        m.location = data.location
    if data.chapter is not None:
        m.chapter = data.chapter
    if data.related_refs is not None:
        m.related_refs = _serialize_list(data.related_refs)
    if data.tags is not None:
        m.tags = _serialize_list(data.tags)
    if data.commentator is not None:
        m.commentator = data.commentator
    if data.source is not None:
        m.source = data.source
    await db.commit()
    await db.refresh(m)
    return m


@router.delete("/{marginalium_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_marginalium(
    marginalium_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Marginalium).where(
            and_(Marginalium.id == marginalium_id, Marginalium.user_id == current_user.id)
        )
    )
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Marginalium not found")
    await db.delete(m)
    await db.commit()


# ── Statistics ─────────────────────────────────────────────────────────────────

class MarginaliaStats(BaseModel):
    total: int
    by_kind: dict[str, int]
    top_tags: list[dict]      # [{"tag": str, "count": int}, ...]
    top_books: list[dict]     # [{"book_id": int, "book_title": str, "count": int}, ...]
    top_commentators: list[dict]  # [{"commentator": str, "count": int}, ...]


@router.get("/stats", response_model=MarginaliaStats)
async def get_marginalia_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return aggregate statistics across all the user's marginalia."""
    stmt = (
        select(Marginalium)
        .where(Marginalium.user_id == current_user.id)
        .order_by(Marginalium.book_id)
    )
    result = await db.execute(stmt)
    items = result.scalars().all()

    if not items:
        return MarginaliaStats(total=0, by_kind={}, top_tags=[], top_books=[], top_commentators=[])

    # Kind counts
    kind_counter: Counter = Counter(m.kind for m in items)

    # Tag frequency
    tag_counter: Counter = Counter()
    for m in items:
        if m.tags:
            try:
                tags = json.loads(m.tags)
                if isinstance(tags, list):
                    tag_counter.update(tags)
            except Exception:
                pass

    # Book counts — bulk-load titles
    book_ids = list({m.book_id for m in items})
    bk_result = await db.execute(select(Book).where(Book.id.in_(book_ids)))
    books_map = {b.id: b.title for b in bk_result.scalars().all()}

    book_counter: Counter = Counter(m.book_id for m in items)

    top_books = [
        {"book_id": bid, "book_title": books_map.get(bid, f"Book {bid}"), "count": cnt}
        for bid, cnt in book_counter.most_common(10)
    ]

    # Commentator counts
    commentator_counter: Counter = Counter(
        m.commentator for m in items if m.commentator
    )

    return MarginaliaStats(
        total=len(items),
        by_kind=dict(kind_counter),
        top_tags=[{"tag": t, "count": c} for t, c in tag_counter.most_common(20)],
        top_books=top_books,
        top_commentators=[
            {"commentator": c, "count": n}
            for c, n in commentator_counter.most_common(10)
        ],
    )


# ── Five Keys Analysis ──────────────────────────────────────────────────────────


def _m_to_dict(m: Marginalium) -> dict:
    return {
        "id": m.id,
        "kind": m.kind,
        "content": m.content,
        "chapter": m.chapter,
        "location": m.location,
        "reading_level": m.reading_level,
        "related_refs": json.loads(m.related_refs) if m.related_refs else [],
        "tags": json.loads(m.tags) if m.tags else [],
        "commentator": m.commentator,
        "source": m.source,
    }


class FiveKeysAnalysis(BaseModel):
    book_id: int
    total: int
    # Key 1 — Center: structural midpoint note
    center: dict | None
    # Key 2 — Contradictions: esoteric notes (often mark contradictions)
    contradictions: list[dict]
    # Key 3 — Silence: chapters present in the book with no marginalia
    silent_chapters: list[str]
    # Key 4 — Repetitions with variation: parallel-kind notes + any with related_refs
    repetitions: list[dict]
    # Key 5 — Boring passages: notes explicitly marking tedious passages
    boring: list[dict]
    # Structural overview
    chapter_counts: dict[str, int]


@router.get("/books/{book_id}/five-keys", response_model=FiveKeysAnalysis)
async def get_five_keys(
    book_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Straussian Five Keys analysis for a book's marginalia.

    Surfaces structural signals derived from the user's notes:
    center passage, contradictions (esoteric notes), silences (uncovered chapters),
    repetitions/parallels, and explicitly boring passages.
    """
    stmt = (
        select(Marginalium)
        .where(
            Marginalium.user_id == current_user.id,
            Marginalium.book_id == book_id,
        )
        .order_by(Marginalium.chapter, Marginalium.location, Marginalium.created_at)
    )
    result = await db.execute(stmt)
    items = list(result.scalars().all())

    if not items:
        return FiveKeysAnalysis(
            book_id=book_id,
            total=0,
            center=None,
            contradictions=[],
            silent_chapters=[],
            repetitions=[],
            boring=[],
            chapter_counts={},
        )

    # Key 1 — Center: the note at the structural midpoint
    center_idx = len(items) // 2
    center = _m_to_dict(items[center_idx])

    # Key 2 — Contradictions: esoteric notes often mark hidden contradictions
    contradictions = [_m_to_dict(m) for m in items if m.kind == "esoteric"]

    # Key 3 — Silence: chapters that appear in adjacent notes but have no notes themselves
    # Approximate: find gaps by sorting chapter labels and flagging large jumps in numbering
    chapters_with_notes = sorted({m.chapter for m in items if m.chapter})
    silent_chapters: list[str] = []
    # Check for roman-numeral or numeric chapter sequences
    num_chapters = []
    for ch in chapters_with_notes:
        m_num = re.search(r"\d+", ch)
        if m_num:
            num_chapters.append((int(m_num.group()), ch))
    num_chapters.sort()
    for i in range(len(num_chapters) - 1):
        n1, label1 = num_chapters[i]
        n2, _ = num_chapters[i + 1]
        for gap in range(n1 + 1, n2):
            gap_label = re.sub(r"\d+", str(gap), label1, count=1)
            silent_chapters.append(gap_label)
    silent_chapters = silent_chapters[:20]  # cap at 20

    # Key 4 — Repetitions with variation: parallel-kind + any note with related_refs
    repetitions = [
        _m_to_dict(m)
        for m in items
        if m.kind == "parallel" or (m.related_refs and m.related_refs != "[]")
    ]

    # Key 5 — Boring passages
    boring = [_m_to_dict(m) for m in items if m.kind == "boring"]

    # Chapter counts
    chapter_counter: Counter = Counter(m.chapter or "Uncategorized" for m in items)

    return FiveKeysAnalysis(
        book_id=book_id,
        total=len(items),
        center=center,
        contradictions=contradictions,
        silent_chapters=silent_chapters,
        repetitions=repetitions,
        boring=boring,
        chapter_counts=dict(chapter_counter),
    )
