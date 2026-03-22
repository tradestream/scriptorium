"""Metadata management endpoints — rename, merge, delete for Authors/Tags/Series/Publishers/Languages."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api.auth import get_current_user
from app.database import get_db
from app.models import User
from app.models.book import Author, Series, Tag
from app.api.browse import AuthorDetail, TagDetail, SeriesDetail

router = APIRouter(prefix="/metadata", tags=["metadata"])


def _require_admin(user: User) -> None:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")


class RenameRequest(BaseModel):
    name: str


class MergeRequest(BaseModel):
    source_ids: list[int]


class SeriesRenameRequest(BaseModel):
    name: str
    description: str | None = None


class FieldRenameRequest(BaseModel):
    old_value: str
    new_value: str


class FieldMergeRequest(BaseModel):
    source_values: list[str]
    target_value: str


class FieldValueDetail(BaseModel):
    value: str
    edition_count: int


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _author_detail(db: AsyncSession, author: Author) -> AuthorDetail:
    count = await db.scalar(
        select(func.count()).select_from(Author).where(Author.id == author.id)
        .join(Author.books)
    ) or 0
    # simpler: use len after loading
    result = await db.execute(
        select(Author).options(joinedload(Author.books)).where(Author.id == author.id)
    )
    a = result.unique().scalar_one()
    return AuthorDetail(id=a.id, name=a.name, description=a.description, book_count=len(a.books))


async def _tag_detail(db: AsyncSession, tag: Tag) -> TagDetail:
    result = await db.execute(
        select(Tag).options(joinedload(Tag.books)).where(Tag.id == tag.id)
    )
    t = result.unique().scalar_one()
    return TagDetail(id=t.id, name=t.name, book_count=len(t.books))


async def _series_detail(db: AsyncSession, series: Series) -> SeriesDetail:
    result = await db.execute(
        select(Series).options(joinedload(Series.books)).where(Series.id == series.id)
    )
    s = result.unique().scalar_one()
    return SeriesDetail(id=s.id, name=s.name, description=s.description, book_count=len(s.books))


# ── Authors ───────────────────────────────────────────────────────────────────

@router.patch("/authors/{author_id}", response_model=AuthorDetail)
async def rename_author(
    author_id: int,
    data: RenameRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    result = await db.execute(select(Author).where(Author.id == author_id))
    author = result.scalar_one_or_none()
    if not author:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Author not found")
    new_name = data.name.strip()
    if not new_name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Name cannot be empty")
    # Check uniqueness
    existing = await db.execute(select(Author).where(Author.name == new_name, Author.id != author_id))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An author with that name already exists")
    author.name = new_name
    await db.commit()
    return await _author_detail(db, author)


@router.post("/authors/{target_id}/merge", response_model=AuthorDetail)
async def merge_authors(
    target_id: int,
    data: MergeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    target_result = await db.execute(
        select(Author).options(joinedload(Author.books)).where(Author.id == target_id)
    )
    target = target_result.unique().scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target author not found")

    for src_id in data.source_ids:
        if src_id == target_id:
            continue
        src_result = await db.execute(
            select(Author).options(joinedload(Author.books)).where(Author.id == src_id)
        )
        source = src_result.unique().scalar_one_or_none()
        if not source:
            continue
        for book in source.books:
            if target not in book.authors:
                book.authors.append(target)
        await db.flush()
        await db.delete(source)

    await db.commit()
    return await _author_detail(db, target)


@router.delete("/authors/{author_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_author(
    author_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    result = await db.execute(
        select(Author).options(joinedload(Author.books)).where(Author.id == author_id)
    )
    author = result.unique().scalar_one_or_none()
    if not author:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Author not found")
    if author.books:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Author has {len(author.books)} associated book(s)",
        )
    await db.delete(author)
    await db.commit()


# ── Tags ──────────────────────────────────────────────────────────────────────

@router.patch("/tags/{tag_id}", response_model=TagDetail)
async def rename_tag(
    tag_id: int,
    data: RenameRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    result = await db.execute(select(Tag).where(Tag.id == tag_id))
    tag = result.scalar_one_or_none()
    if not tag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")
    new_name = data.name.strip().lower()
    if not new_name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Name cannot be empty")
    existing = await db.execute(select(Tag).where(Tag.name == new_name, Tag.id != tag_id))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A tag with that name already exists")
    tag.name = new_name
    await db.commit()
    return await _tag_detail(db, tag)


@router.post("/tags/{target_id}/merge", response_model=TagDetail)
async def merge_tags(
    target_id: int,
    data: MergeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    target_result = await db.execute(
        select(Tag).options(joinedload(Tag.books)).where(Tag.id == target_id)
    )
    target = target_result.unique().scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target tag not found")

    for src_id in data.source_ids:
        if src_id == target_id:
            continue
        src_result = await db.execute(
            select(Tag).options(joinedload(Tag.books)).where(Tag.id == src_id)
        )
        source = src_result.unique().scalar_one_or_none()
        if not source:
            continue
        for book in source.books:
            if target not in book.tags:
                book.tags.append(target)
        await db.flush()
        await db.delete(source)

    await db.commit()
    return await _tag_detail(db, target)


@router.delete("/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag(
    tag_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    result = await db.execute(
        select(Tag).options(joinedload(Tag.books)).where(Tag.id == tag_id)
    )
    tag = result.unique().scalar_one_or_none()
    if not tag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")
    if tag.books:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Tag has {len(tag.books)} associated book(s)",
        )
    await db.delete(tag)
    await db.commit()


# ── Series ────────────────────────────────────────────────────────────────────

@router.patch("/series/{series_id}", response_model=SeriesDetail)
async def rename_series(
    series_id: int,
    data: SeriesRenameRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    result = await db.execute(select(Series).where(Series.id == series_id))
    series = result.scalar_one_or_none()
    if not series:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Series not found")
    new_name = data.name.strip()
    if not new_name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Name cannot be empty")
    existing = await db.execute(select(Series).where(Series.name == new_name, Series.id != series_id))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A series with that name already exists")
    series.name = new_name
    if data.description is not None:
        series.description = data.description
    await db.commit()
    return await _series_detail(db, series)


@router.post("/series/{target_id}/merge", response_model=SeriesDetail)
async def merge_series(
    target_id: int,
    data: MergeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    target_result = await db.execute(
        select(Series).options(joinedload(Series.books)).where(Series.id == target_id)
    )
    target = target_result.unique().scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target series not found")

    for src_id in data.source_ids:
        if src_id == target_id:
            continue
        src_result = await db.execute(
            select(Series).options(joinedload(Series.books)).where(Series.id == src_id)
        )
        source = src_result.unique().scalar_one_or_none()
        if not source:
            continue
        for book in source.books:
            if target not in book.series:
                book.series.append(target)
        await db.flush()
        await db.delete(source)

    await db.commit()
    return await _series_detail(db, target)


@router.delete("/series/{series_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_series_entity(
    series_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    result = await db.execute(
        select(Series).options(joinedload(Series.books)).where(Series.id == series_id)
    )
    series = result.unique().scalar_one_or_none()
    if not series:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Series not found")
    if series.books:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Series has {len(series.books)} associated book(s)",
        )
    await db.delete(series)
    await db.commit()


# ── Publishers ───────────────────────────────────────────────────────────────

@router.get("/publishers", response_model=list[FieldValueDetail])
async def list_publishers(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all distinct publisher values with edition counts."""
    from app.models.edition import Edition
    result = await db.execute(
        select(Edition.publisher, func.count(Edition.id).label("cnt"))
        .where(Edition.publisher.isnot(None), Edition.publisher != "")
        .group_by(Edition.publisher)
        .order_by(func.count(Edition.id).desc())
    )
    return [FieldValueDetail(value=row[0], edition_count=row[1]) for row in result.all()]


@router.post("/publishers/rename", response_model=FieldValueDetail)
async def rename_publisher(
    data: FieldRenameRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Rename all editions with one publisher value to another."""
    _require_admin(current_user)
    new = data.new_value.strip()
    if not new:
        raise HTTPException(status_code=422, detail="New value cannot be empty")
    result = await db.execute(
        text("UPDATE editions SET publisher = :new WHERE publisher = :old"),
        {"new": new, "old": data.old_value},
    )
    await db.commit()
    from app.models.edition import Edition
    count = await db.scalar(
        select(func.count(Edition.id)).where(Edition.publisher == new)
    )
    return FieldValueDetail(value=new, edition_count=count or 0)


@router.post("/publishers/merge", response_model=FieldValueDetail)
async def merge_publishers(
    data: FieldMergeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Merge multiple publisher values into a target value."""
    _require_admin(current_user)
    target = data.target_value.strip()
    if not target:
        raise HTTPException(status_code=422, detail="Target value cannot be empty")
    for src in data.source_values:
        if src != target:
            await db.execute(
                text("UPDATE editions SET publisher = :target WHERE publisher = :src"),
                {"target": target, "src": src},
            )
    await db.commit()
    from app.models.edition import Edition
    count = await db.scalar(
        select(func.count(Edition.id)).where(Edition.publisher == target)
    )
    return FieldValueDetail(value=target, edition_count=count or 0)


# ── Languages ────────────────────────────────────────────────────────────────

@router.get("/languages", response_model=list[FieldValueDetail])
async def list_languages(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all distinct language values with edition counts."""
    from app.models.edition import Edition
    result = await db.execute(
        select(Edition.language, func.count(Edition.id).label("cnt"))
        .where(Edition.language.isnot(None), Edition.language != "")
        .group_by(Edition.language)
        .order_by(func.count(Edition.id).desc())
    )
    return [FieldValueDetail(value=row[0], edition_count=row[1]) for row in result.all()]


@router.post("/languages/rename", response_model=FieldValueDetail)
async def rename_language(
    data: FieldRenameRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Rename all editions with one language value to another."""
    _require_admin(current_user)
    new = data.new_value.strip()
    if not new:
        raise HTTPException(status_code=422, detail="New value cannot be empty")
    result = await db.execute(
        text("UPDATE editions SET language = :new WHERE language = :old"),
        {"new": new, "old": data.old_value},
    )
    await db.commit()
    from app.models.edition import Edition
    count = await db.scalar(
        select(func.count(Edition.id)).where(Edition.language == new)
    )
    return FieldValueDetail(value=new, edition_count=count or 0)


@router.post("/languages/merge", response_model=FieldValueDetail)
async def merge_languages(
    data: FieldMergeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Merge multiple language values into a target value."""
    _require_admin(current_user)
    target = data.target_value.strip()
    if not target:
        raise HTTPException(status_code=422, detail="Target value cannot be empty")
    for src in data.source_values:
        if src != target:
            await db.execute(
                text("UPDATE editions SET language = :target WHERE language = :src"),
                {"target": target, "src": src},
            )
    await db.commit()
    from app.models.edition import Edition
    count = await db.scalar(
        select(func.count(Edition.id)).where(Edition.language == target)
    )
    return FieldValueDetail(value=target, edition_count=count or 0)
