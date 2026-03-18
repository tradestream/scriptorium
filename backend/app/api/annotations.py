import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api.auth import get_current_user
from app.database import get_db
from app.models import Book, User
from app.models.annotation import Annotation
from app.models.work import Work
from app.schemas.annotation import AnnotationCreate, AnnotationRead, AnnotationUpdate, AnnotationWithBook

router = APIRouter(prefix="/annotations", tags=["annotations"])


@router.get("", response_model=list[AnnotationRead])
async def list_annotations(
    book_id: int = Query(..., description="Filter by book"),
    annotation_type: str | None = Query(default=None, alias="type"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List annotations for a book."""
    stmt = select(Annotation).where(
        Annotation.user_id == current_user.id,
        Annotation.edition_id == book_id,
    )
    if annotation_type:
        stmt = stmt.where(Annotation.type == annotation_type)
    stmt = stmt.order_by(Annotation.created_at)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/mine", response_model=list[AnnotationWithBook])
async def list_my_annotations(
    annotation_type: str | None = Query(default=None, alias="type"),
    q: str | None = Query(default=None, description="Search annotation content"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """All annotations for the current user across all books, with book metadata."""
    stmt = select(Annotation).where(Annotation.user_id == current_user.id)
    if annotation_type:
        stmt = stmt.where(Annotation.type == annotation_type)
    if q:
        stmt = stmt.where(Annotation.content.ilike(f"%{q}%"))
    stmt = stmt.order_by(Annotation.created_at.desc())
    result = await db.execute(stmt)
    annotations = result.scalars().all()

    # Bulk-load books (with authors) to avoid N+1
    book_ids = list({a.edition_id for a in annotations})
    books_map: dict[int, Book] = {}
    if book_ids:
        bk_result = await db.execute(
            select(Book).where(Book.id.in_(book_ids)).options(
                joinedload(Book.work).options(joinedload(Work.authors))
            )
        )
        for b in bk_result.unique().scalars().all():
            books_map[b.id] = b

    out = []
    for ann in annotations:
        bk = books_map.get(ann.edition_id)
        out.append(
            {
                "id": ann.id,
                "user_id": ann.user_id,
                "book_id": ann.edition_id,
                "file_id": ann.file_id,
                "type": ann.type,
                "content": ann.content,
                "location": ann.location,
                "chapter": ann.chapter,
                "color": ann.color,
                "created_at": ann.created_at,
                "updated_at": ann.updated_at,
                "book_title": bk.title if bk else None,
                "book_author": bk.authors[0].name if bk and bk.authors else None,
            }
        )
    return out


@router.post("", response_model=AnnotationRead, status_code=status.HTTP_201_CREATED)
async def create_annotation(
    data: AnnotationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    annotation = Annotation(
        user_id=current_user.id,
        edition_id=data.book_id,
        file_id=data.file_id,
        type=data.type,
        content=data.content,
        location=data.location,
        chapter=data.chapter,
        color=data.color or "yellow",
        tags=json.dumps(data.tags) if data.tags else None,
        related_refs=json.dumps(data.related_refs) if data.related_refs else None,
        commentator=data.commentator,
        source=data.source,
    )
    db.add(annotation)
    await db.commit()
    await db.refresh(annotation)
    return annotation


@router.put("/{annotation_id}", response_model=AnnotationRead)
async def update_annotation(
    annotation_id: int,
    data: AnnotationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Annotation).where(
            and_(Annotation.id == annotation_id, Annotation.user_id == current_user.id)
        )
    )
    annotation = result.scalar_one_or_none()
    if not annotation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Annotation not found")
    if data.content is not None:
        annotation.content = data.content
    if data.color is not None:
        annotation.color = data.color
    if data.chapter is not None:
        annotation.chapter = data.chapter
    if data.tags is not None:
        annotation.tags = json.dumps(data.tags)
    if data.related_refs is not None:
        annotation.related_refs = json.dumps(data.related_refs)
    if data.commentator is not None:
        annotation.commentator = data.commentator
    if data.source is not None:
        annotation.source = data.source
    await db.commit()
    await db.refresh(annotation)
    return annotation


@router.delete("/{annotation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_annotation(
    annotation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Annotation).where(
            and_(Annotation.id == annotation_id, Annotation.user_id == current_user.id)
        )
    )
    annotation = result.scalar_one_or_none()
    if not annotation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Annotation not found")
    await db.delete(annotation)
    await db.commit()


# ── Export ─────────────────────────────────────────────────────────────────────

@router.get("/export", response_class=PlainTextResponse)
async def export_annotations(
    book_id: int = Query(...),
    fmt: str = Query(default="yaml", description="yaml or json"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export all annotations + marginalia for a book as YAML or JSON."""
    from app.models.marginalium import Marginalium

    ann_result = await db.execute(
        select(Annotation).where(
            Annotation.user_id == current_user.id,
            Annotation.edition_id == book_id,
        ).order_by(Annotation.created_at)
    )
    annotations = ann_result.scalars().all()

    mar_result = await db.execute(
        select(Marginalium).where(
            Marginalium.user_id == current_user.id,
            Marginalium.edition_id == book_id,
        ).order_by(Marginalium.created_at)
    )
    marginalia = mar_result.scalars().all()

    def _list(v: str | None) -> list:
        if not v:
            return []
        try:
            return json.loads(v)
        except Exception:
            return [s.strip() for s in v.split(",") if s.strip()]

    data = {
        "book_id": book_id,
        "annotations": [
            {
                "id": a.id,
                "type": a.type,
                "content": a.content,
                "location": a.location,
                "chapter": a.chapter,
                "color": a.color,
                "tags": _list(a.tags),
                "related_refs": _list(a.related_refs),
                "commentator": a.commentator,
                "source": a.source,
                "created_at": a.created_at.isoformat(),
            }
            for a in annotations
        ],
        "marginalia": [
            {
                "id": m.id,
                "kind": m.kind,
                "content": m.content,
                "location": m.location,
                "chapter": m.chapter,
                "tags": _list(m.tags),
                "related_refs": _list(m.related_refs),
                "commentator": m.commentator,
                "source": m.source,
                "created_at": m.created_at.isoformat(),
            }
            for m in marginalia
        ],
    }

    if fmt == "json":
        return PlainTextResponse(
            json.dumps(data, indent=2, ensure_ascii=False),
            media_type="application/json",
        )

    # YAML output
    try:
        import yaml
        return PlainTextResponse(
            yaml.dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False),
            media_type="text/yaml",
        )
    except ImportError:
        # Fall back to JSON if PyYAML not installed
        return PlainTextResponse(
            json.dumps(data, indent=2, ensure_ascii=False),
            media_type="application/json",
        )
