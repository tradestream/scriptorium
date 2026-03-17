"""Notebooks — named cross-book collections of marginalia."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.database import get_db
from app.models import Book, User
from app.models.marginalium import Marginalium
from app.models.notebook import Notebook, NotebookEntry

router = APIRouter(prefix="/notebooks", tags=["notebooks"])


# ── Schemas ────────────────────────────────────────────────────────────────────

class NotebookCreate(BaseModel):
    name: str
    description: Optional[str] = None


class NotebookUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class NotebookRead(BaseModel):
    id: int
    user_id: int
    name: str
    description: Optional[str] = None
    entry_count: int = 0
    created_at: str
    updated_at: str


class EntryCreate(BaseModel):
    marginalium_id: int
    note: Optional[str] = None


class EntryRead(BaseModel):
    id: int
    notebook_id: int
    marginalium_id: int
    note: Optional[str] = None
    created_at: str
    # Marginalium fields
    kind: str
    content: str
    chapter: Optional[str] = None
    location: Optional[str] = None
    reading_level: Optional[str] = None
    book_id: int
    book_title: Optional[str] = None


# ── Notebook CRUD ──────────────────────────────────────────────────────────────

@router.get("", response_model=list[NotebookRead])
async def list_notebooks(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Notebook).where(Notebook.user_id == current_user.id).order_by(Notebook.created_at.desc())
    )
    notebooks = result.scalars().all()

    # Count entries per notebook
    counts: dict[int, int] = {}
    if notebooks:
        entry_result = await db.execute(
            select(NotebookEntry).where(
                NotebookEntry.notebook_id.in_([n.id for n in notebooks])
            )
        )
        for e in entry_result.scalars().all():
            counts[e.notebook_id] = counts.get(e.notebook_id, 0) + 1

    return [
        NotebookRead(
            id=n.id,
            user_id=n.user_id,
            name=n.name,
            description=n.description,
            entry_count=counts.get(n.id, 0),
            created_at=n.created_at.isoformat(),
            updated_at=n.updated_at.isoformat(),
        )
        for n in notebooks
    ]


@router.post("", response_model=NotebookRead, status_code=status.HTTP_201_CREATED)
async def create_notebook(
    data: NotebookCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    nb = Notebook(user_id=current_user.id, name=data.name.strip(), description=data.description)
    db.add(nb)
    await db.commit()
    await db.refresh(nb)
    return NotebookRead(
        id=nb.id,
        user_id=nb.user_id,
        name=nb.name,
        description=nb.description,
        entry_count=0,
        created_at=nb.created_at.isoformat(),
        updated_at=nb.updated_at.isoformat(),
    )


@router.put("/{notebook_id}", response_model=NotebookRead)
async def update_notebook(
    notebook_id: int,
    data: NotebookUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Notebook).where(
            and_(Notebook.id == notebook_id, Notebook.user_id == current_user.id)
        )
    )
    nb = result.scalar_one_or_none()
    if not nb:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notebook not found")
    if data.name is not None:
        nb.name = data.name.strip()
    if data.description is not None:
        nb.description = data.description
    await db.commit()
    await db.refresh(nb)

    count_result = await db.execute(
        select(NotebookEntry).where(NotebookEntry.notebook_id == nb.id)
    )
    entry_count = len(count_result.scalars().all())

    return NotebookRead(
        id=nb.id,
        user_id=nb.user_id,
        name=nb.name,
        description=nb.description,
        entry_count=entry_count,
        created_at=nb.created_at.isoformat(),
        updated_at=nb.updated_at.isoformat(),
    )


@router.delete("/{notebook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notebook(
    notebook_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Notebook).where(
            and_(Notebook.id == notebook_id, Notebook.user_id == current_user.id)
        )
    )
    nb = result.scalar_one_or_none()
    if not nb:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notebook not found")
    await db.delete(nb)
    await db.commit()


# ── Entries ────────────────────────────────────────────────────────────────────

@router.get("/{notebook_id}/entries", response_model=list[EntryRead])
async def list_entries(
    notebook_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify ownership
    nb_result = await db.execute(
        select(Notebook).where(
            and_(Notebook.id == notebook_id, Notebook.user_id == current_user.id)
        )
    )
    if not nb_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notebook not found")

    entry_result = await db.execute(
        select(NotebookEntry)
        .where(NotebookEntry.notebook_id == notebook_id)
        .order_by(NotebookEntry.created_at)
    )
    entries = entry_result.scalars().all()

    # Load marginalia
    m_ids = [e.marginalium_id for e in entries]
    margins: dict[int, Marginalium] = {}
    if m_ids:
        m_result = await db.execute(select(Marginalium).where(Marginalium.id.in_(m_ids)))
        for m in m_result.scalars().all():
            margins[m.id] = m

    # Load books
    book_ids = list({m.edition_id for m in margins.values()})
    books_map: dict[int, Book] = {}
    if book_ids:
        bk_result = await db.execute(select(Book).where(Book.id.in_(book_ids)))
        for b in bk_result.scalars().all():
            books_map[b.id] = b

    out = []
    for e in entries:
        m = margins.get(e.marginalium_id)
        if not m:
            continue
        bk = books_map.get(m.edition_id)
        out.append(
            EntryRead(
                id=e.id,
                notebook_id=e.notebook_id,
                marginalium_id=e.marginalium_id,
                note=e.note,
                created_at=e.created_at.isoformat(),
                kind=m.kind,
                content=m.content,
                chapter=m.chapter,
                location=m.location,
                reading_level=m.reading_level,
                book_id=m.edition_id,
                book_title=bk.title if bk else None,
            )
        )
    return out


@router.post("/{notebook_id}/entries", response_model=EntryRead, status_code=status.HTTP_201_CREATED)
async def add_entry(
    notebook_id: int,
    data: EntryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify notebook ownership
    nb_result = await db.execute(
        select(Notebook).where(
            and_(Notebook.id == notebook_id, Notebook.user_id == current_user.id)
        )
    )
    if not nb_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notebook not found")

    # Verify marginalium belongs to user
    m_result = await db.execute(
        select(Marginalium).where(
            and_(
                Marginalium.id == data.marginalium_id,
                Marginalium.user_id == current_user.id,
            )
        )
    )
    m = m_result.scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Marginalium not found")

    # Check for duplicate
    dup = await db.execute(
        select(NotebookEntry).where(
            and_(
                NotebookEntry.notebook_id == notebook_id,
                NotebookEntry.marginalium_id == data.marginalium_id,
            )
        )
    )
    if dup.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Already in notebook"
        )

    entry = NotebookEntry(
        notebook_id=notebook_id,
        marginalium_id=data.marginalium_id,
        note=data.note,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)

    bk = await db.get(Book, m.edition_id)

    return EntryRead(
        id=entry.id,
        notebook_id=entry.notebook_id,
        marginalium_id=entry.marginalium_id,
        note=entry.note,
        created_at=entry.created_at.isoformat(),
        kind=m.kind,
        content=m.content,
        chapter=m.chapter,
        location=m.location,
        reading_level=m.reading_level,
        book_id=m.edition_id,
        book_title=bk.title if bk else None,
    )


@router.delete("/{notebook_id}/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_entry(
    notebook_id: int,
    entry_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify notebook ownership
    nb_result = await db.execute(
        select(Notebook).where(
            and_(Notebook.id == notebook_id, Notebook.user_id == current_user.id)
        )
    )
    if not nb_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notebook not found")

    entry_result = await db.execute(
        select(NotebookEntry).where(
            and_(NotebookEntry.id == entry_id, NotebookEntry.notebook_id == notebook_id)
        )
    )
    entry = entry_result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")
    await db.delete(entry)
    await db.commit()
