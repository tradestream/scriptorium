import logging
import uuid
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from pydantic import BaseModel
from fastapi.responses import FileResponse
from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.database import get_db
from app.models import Author, Edition, EditionFile, EditionContributor, Library, Shelf, ShelfBook, Tag, Series, User
from app.models.work import Work, WorkContributor, work_series
from app.models.work import work_authors, work_tags
from app.schemas.book import BookCreate, BookListResponse, BookRead, BookUpdate
from app.schemas.shelf import ShelfRead
from app.utils.files import calculate_file_hash, get_file_format, get_file_size, is_book_file

from .auth import assert_library_access, get_accessible_library_ids, get_current_user

router = APIRouter(prefix="/books")


def _edition_options():
    """Eager-load all relationships needed for BookRead serialization."""
    return [
        joinedload(Edition.work).options(
            joinedload(Work.authors),
            joinedload(Work.tags),
            joinedload(Work.series),
            joinedload(Work.contributors),
        ),
        joinedload(Edition.files),
        joinedload(Edition.contributors),
        joinedload(Edition.location_ref),
    ]


@router.get("", response_model=BookListResponse)
async def list_books(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=5000),
    library_id: Optional[int] = None,
    include_hidden: bool = False,
    search: Optional[str] = None,
    author_id: Optional[int] = None,
    tag_id: Optional[int] = None,
    abs_linked: bool = False,
    format: Optional[str] = None,
    sort_by: str = Query("date_added", pattern="^(date_added|title)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List books with pagination and filtering.
    By default, books from hidden libraries are excluded unless
    a specific library_id is provided or include_hidden=true."""
    # Always join to Work so we can filter/sort on work fields
    stmt = select(Edition).join(Edition.work)

    # Per-user library access filter
    accessible_ids = await get_accessible_library_ids(db, current_user)
    if accessible_ids is not None:
        stmt = stmt.where(Edition.library_id.in_(accessible_ids))

    # Apply filters
    if library_id:
        stmt = stmt.where(Edition.library_id == library_id)
    elif not include_hidden:
        # Exclude editions from hidden libraries in general listing
        hidden_lib_ids = select(Library.id).where(Library.is_hidden == True)
        stmt = stmt.where(Edition.library_id.notin_(hidden_lib_ids))

    if search:
        search_pattern = f"%{search}%"
        stmt = stmt.where(
            or_(
                Work.title.ilike(search_pattern),
                Work.description.ilike(search_pattern),
            )
        )

    if author_id:
        stmt = stmt.where(Edition.work.has(Work.authors.any(id=author_id)))

    if tag_id:
        stmt = stmt.where(Edition.work.has(Work.tags.any(id=tag_id)))

    if abs_linked:
        stmt = stmt.where(Edition.abs_item_id.isnot(None))

    if format:
        from app.models.edition import EditionFile
        stmt = stmt.where(Edition.files.any(EditionFile.format.ilike(format)))

    # Get total count (same filters as main query, without pagination)
    count_stmt = select(func.count()).select_from(stmt.subquery())
    count = (await db.scalar(count_stmt)) or 0

    # Eager load relationships
    stmt = stmt.options(*_edition_options())

    # Ordering
    if sort_by == "title":
        stmt = stmt.order_by(Work.title.asc())
    else:
        stmt = stmt.order_by(Edition.created_at.desc())

    # Pagination
    stmt = stmt.limit(limit).offset(skip)

    result = await db.execute(stmt)
    editions = result.unique().scalars().all()

    # Batch-fetch reading statuses from the unified ReadingState (work-keyed)
    # joined back through Edition. One edition per Work in the result list,
    # so the join is 1:1 within this batch.
    from app.models.reading import ReadingState
    edition_ids = [e.id for e in editions]
    if edition_ids:
        rs_result = await db.execute(
            select(Edition.id, ReadingState.status)
            .join(ReadingState, ReadingState.work_id == Edition.work_id)
            .where(
                ReadingState.user_id == current_user.id,
                Edition.id.in_(edition_ids),
            )
        )
        status_map = {eid: st for eid, st in rs_result.all()}
    else:
        status_map = {}

    items = []
    for e in editions:
        book = BookRead.model_validate(e)
        book.reading_status = status_map.get(e.id)
        items.append(book)

    return BookListResponse(
        items=items,
        total=count,
        skip=skip,
        limit=limit,
    )


@router.get("/{book_id}", response_model=BookRead)
async def get_book(
    book_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific book by ID."""
    stmt = select(Edition).where(Edition.id == book_id).options(*_edition_options())

    result = await db.execute(stmt)
    edition = result.unique().scalar_one_or_none()

    if not edition:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")

    # Check library access
    accessible_ids = await get_accessible_library_ids(db, current_user)
    if accessible_ids is not None and edition.library_id not in accessible_ids:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")

    return BookRead.model_validate(edition)


@router.get("/lookup")
async def lookup_metadata(
    title: str = "",
    author: str = "",
    isbn: str = "",
    _current_user: User = Depends(get_current_user),
):
    """Fetch enriched metadata from external providers without creating a book.

    Used by the manual book-add form to pre-fill fields before saving.
    """
    if not title and not isbn:
        return {}
    try:
        from app.services.metadata_enrichment import enrichment_service
        result = await enrichment_service.enrich(
            title=title or (isbn or ""),
            authors=[author] if author else [],
            isbn=isbn or None,
        )
        return result or {}
    except Exception:
        return {}


@router.post("", response_model=BookRead, status_code=status.HTTP_201_CREATED)
async def create_book(
    book_data: BookCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new book record (Work + Edition)."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can create books",
        )

    # Verify library exists
    stmt = select(Library).where(Library.id == book_data.library_id)
    result = await db.execute(stmt)
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Library not found",
        )

    # Create Work
    work = Work(
        uuid=str(uuid.uuid4()),
        title=book_data.title,
        subtitle=book_data.subtitle,
        description=book_data.description,
        language=book_data.language,
    )

    # Add Work relationships by ID
    if book_data.author_ids:
        stmt = select(Author).where(Author.id.in_(book_data.author_ids))
        result = await db.execute(stmt)
        work.authors.extend(result.scalars().all())

    if book_data.tag_ids:
        stmt = select(Tag).where(Tag.id.in_(book_data.tag_ids))
        result = await db.execute(stmt)
        work.tags.extend(result.scalars().all())

    if book_data.series_ids:
        stmt = select(Series).where(Series.id.in_(book_data.series_ids))
        result = await db.execute(stmt)
        work.series.extend(result.scalars().all())

    # Resolve by name (create-or-get)
    for name in book_data.author_names:
        name = name.strip()
        if not name:
            continue
        r = await db.execute(select(Author).where(Author.name == name))
        author = r.scalar_one_or_none() or Author(name=name)
        if not author.id:
            db.add(author)
            await db.flush()
        if author not in work.authors:
            work.authors.append(author)

    for name in book_data.tag_names:
        name = name.strip().lower()
        if not name:
            continue
        r = await db.execute(select(Tag).where(Tag.name == name))
        tag = r.scalar_one_or_none() or Tag(name=name)
        if not tag.id:
            db.add(tag)
            await db.flush()
        if tag not in work.tags:
            work.tags.append(tag)

    db.add(work)
    await db.flush()

    # Create Edition (isbn already normalized to ISBN-13 by schema validator)
    from app.utils.isbn import normalize as _normalize_isbn
    _isbn13 = book_data.isbn
    _, _isbn10 = _normalize_isbn(book_data.isbn) if book_data.isbn else (None, None)

    edition = Edition(
        uuid=str(uuid.uuid4()),
        work_id=work.id,
        isbn=_isbn13,
        isbn_10=_isbn10,
        publisher=book_data.publisher,
        published_date=book_data.published_date,
        physical_copy=book_data.physical_copy,
        binding=book_data.binding,
        condition=book_data.condition,
        purchase_price=book_data.purchase_price,
        purchase_date=book_data.purchase_date,
        purchase_from=book_data.purchase_from,
        location=book_data.location,
        location_id=book_data.location_id,
        library_id=book_data.library_id,
    )
    db.add(edition)
    await db.commit()

    # Re-fetch with eager-loaded relationships for serialization
    result = await db.execute(
        select(Edition)
        .where(Edition.id == edition.id)
        .options(*_edition_options())
    )
    edition = result.unique().scalar_one()

    return BookRead.model_validate(edition)


@router.put("/{book_id}", response_model=BookRead)
async def update_book(
    book_id: int,
    book_data: BookUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a book record."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can update books",
        )

    stmt = select(Edition).where(Edition.id == book_id).options(*_edition_options())
    result = await db.execute(stmt)
    edition = result.unique().scalar_one_or_none()

    if not edition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Book not found",
        )

    work = edition.work

    # Update Work fields
    if book_data.title is not None:
        work.title = book_data.title
    if book_data.subtitle is not None:
        work.subtitle = book_data.subtitle
    if book_data.description is not None:
        work.description = book_data.description

    # Update Edition fields
    if book_data.isbn is not None:
        edition.isbn = book_data.isbn  # already normalized to ISBN-13 by schema
        from app.utils.isbn import normalize as _normalize_isbn
        _, isbn10 = _normalize_isbn(book_data.isbn)
        edition.isbn_10 = isbn10
    if book_data.language is not None:
        edition.language = book_data.language
    if book_data.published_date is not None:
        edition.published_date = book_data.published_date
    if book_data.publisher is not None:
        edition.publisher = book_data.publisher
    if book_data.physical_copy is not None:
        edition.physical_copy = book_data.physical_copy
    if book_data.binding is not None:
        edition.binding = book_data.binding or None
    if book_data.condition is not None:
        edition.condition = book_data.condition or None
    if book_data.purchase_price is not None:
        edition.purchase_price = book_data.purchase_price
    if book_data.purchase_date is not None:
        edition.purchase_date = book_data.purchase_date
    if book_data.purchase_from is not None:
        edition.purchase_from = book_data.purchase_from or None
    if book_data.location is not None:
        edition.location = book_data.location
    if book_data.location_id is not None:
        edition.location_id = book_data.location_id if book_data.location_id != 0 else None

    # Update Work relationships — name-based takes priority over ID-based
    if book_data.author_names is not None:
        work.authors = await _get_or_create(db, Author, "name", book_data.author_names)
    elif book_data.author_ids is not None:
        r = await db.execute(select(Author).where(Author.id.in_(book_data.author_ids)))
        work.authors = list(r.scalars().all())

    if book_data.tag_names is not None:
        work.tags = await _get_or_create(db, Tag, "name", book_data.tag_names)
    elif book_data.tag_ids is not None:
        r = await db.execute(select(Tag).where(Tag.id.in_(book_data.tag_ids)))
        work.tags = list(r.scalars().all())

    if book_data.series_names is not None:
        work.series = await _get_or_create(db, Series, "name", book_data.series_names)
    elif book_data.series_ids is not None:
        r = await db.execute(select(Series).where(Series.id.in_(book_data.series_ids)))
        work.series = list(r.scalars().all())

    # Update contributors by role (edition-level: translator; work-level: editor/illustrator/colorist)
    contributor_fields = {
        "translator": book_data.translator_names,
        "editor": book_data.editor_names,
        "illustrator": book_data.illustrator_names,
        "colorist": book_data.colorist_names,
    }
    for role, names in contributor_fields.items():
        if names is not None:
            if role == "translator":
                # Edition-level contributor
                await db.execute(
                    delete(EditionContributor).where(
                        EditionContributor.edition_id == edition.id,
                        EditionContributor.role == role,
                    )
                )
                for name in names:
                    name = name.strip()
                    if name:
                        db.add(EditionContributor(edition_id=edition.id, name=name, role=role))
            else:
                # Work-level contributor
                await db.execute(
                    delete(WorkContributor).where(
                        WorkContributor.work_id == work.id,
                        WorkContributor.role == role,
                    )
                )
                for name in names:
                    name = name.strip()
                    if name:
                        db.add(WorkContributor(work_id=work.id, name=name, role=role))

    await db.commit()
    await db.refresh(edition)

    # Re-index in FTS5
    from app.services.search import search_service
    await db.refresh(work, ["authors", "contributors"])
    await search_service.index_work(db, work, [a.name for a in work.authors])
    await db.commit()

    return BookRead.model_validate(edition)


class BulkEditRequest(BaseModel):
    """Bulk-edit metadata across multiple books."""
    edition_ids: list[int]
    # Fields to set (None = don't change)
    author_names: Optional[list[str]] = None
    tag_names: Optional[list[str]] = None
    series_names: Optional[list[str]] = None
    publisher: Optional[str] = None
    language: Optional[str] = None
    # Merge mode: True = add to existing, False = replace
    merge_authors: bool = True
    merge_tags: bool = True
    merge_series: bool = True


@router.put("/bulk-edit", status_code=status.HTTP_200_OK)
async def bulk_edit_books(
    req: BulkEditRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update metadata for multiple books at once.

    Supports setting authors, tags, series, publisher, language across
    a batch of selected books. Merge mode adds to existing values;
    replace mode overwrites them.
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")

    from app.services.search import search_service

    updated = 0
    failed = 0

    for edition_id in req.edition_ids:
        try:
            stmt = select(Edition).where(Edition.id == edition_id).options(*_edition_options())
            result = await db.execute(stmt)
            edition = result.unique().scalar_one_or_none()
            if not edition:
                failed += 1
                continue

            work = edition.work

            # Authors
            if req.author_names is not None:
                new_authors = await _get_or_create(db, Author, "name", req.author_names)
                if req.merge_authors:
                    existing_ids = {a.id for a in work.authors}
                    for a in new_authors:
                        if a.id not in existing_ids:
                            work.authors.append(a)
                else:
                    work.authors = new_authors

            # Tags
            if req.tag_names is not None:
                new_tags = await _get_or_create(db, Tag, "name", req.tag_names)
                if req.merge_tags:
                    existing_ids = {t.id for t in work.tags}
                    for t in new_tags:
                        if t.id not in existing_ids:
                            work.tags.append(t)
                else:
                    work.tags = new_tags

            # Series
            if req.series_names is not None:
                new_series = await _get_or_create(db, Series, "name", req.series_names)
                if req.merge_series:
                    existing_ids = {s.id for s in work.series}
                    for s in new_series:
                        if s.id not in existing_ids:
                            work.series.append(s)
                else:
                    work.series = new_series

            # Publisher
            if req.publisher is not None:
                edition.publisher = req.publisher

            # Language
            if req.language is not None:
                edition.language = req.language

            await db.flush()
            await search_service.index_work(db, work, [a.name for a in work.authors])
            updated += 1

        except Exception as exc:
            logger.warning("Bulk edit failed for edition %d: %s", edition_id, exc)
            failed += 1

    await db.commit()
    return {"updated": updated, "failed": failed}


class LockedFieldsUpdate(BaseModel):
    locked_fields: list[str]  # e.g. ["title", "authors", "description"]


@router.patch("/{book_id}/locked-fields")
async def update_locked_fields(
    book_id: int,
    data: LockedFieldsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Set which metadata fields are locked (protected from enrichment/scanning overwrites). Admin only."""
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    result = await db.execute(select(Edition).where(Edition.id == book_id))
    edition = result.scalar_one_or_none()
    if not edition:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    import json
    edition.locked_fields = json.dumps(data.locked_fields) if data.locked_fields else None
    await db.commit()
    return {"locked_fields": data.locked_fields}


@router.delete("/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_book(
    book_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a book record."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can delete books",
        )

    stmt = select(Edition).where(Edition.id == book_id)
    result = await db.execute(stmt)
    edition = result.scalar_one_or_none()

    if not edition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Book not found",
        )

    from app.services.audit import log_action
    title = edition.work.title if edition.work else f"Edition {book_id}"
    await log_action(db, "book.delete", user_id=current_user.id,
                     entity_type="edition", entity_id=book_id, detail=title)
    await db.delete(edition)
    await db.commit()


@router.get("/{book_id}/cover")
async def get_book_cover(
    book_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Serve the book's cover image."""
    from app.config import get_settings
    from app.services.file_streaming import stream_file_response
    settings = get_settings()

    stmt = select(Edition).where(Edition.id == book_id)
    result = await db.execute(stmt)
    edition = result.scalar_one_or_none()

    if not edition or not edition.cover_hash or not edition.cover_format:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No cover available")

    await assert_library_access(db, current_user, edition.library_id)

    cover_path = Path(settings.COVERS_PATH) / f"{edition.uuid}.{edition.cover_format}"

    media_type = f"image/{edition.cover_format}" if edition.cover_format != "jpg" else "image/jpeg"
    # Covers change when the user re-uploads or enrichment fetches a new image;
    # rely on the ETag for revalidation, allow short browser caching.
    return stream_file_response(
        request,
        cover_path,
        media_type=media_type,
        cache_control="private, max-age=300",
        etag_salt=edition.cover_hash,
    )


@router.put("/{book_id}/cover", response_model=BookRead)
async def upload_book_cover(
    book_id: int,
    cover: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload a new cover image for a book."""
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")

    stmt = select(Edition).where(Edition.id == book_id)
    result = await db.execute(stmt)
    edition = result.scalar_one_or_none()
    if not edition:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")

    cover_bytes = await cover.read()
    if not cover_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")

    from app.services.covers import cover_service
    # Remove old cover if any
    if edition.cover_format:
        await cover_service.delete_cover(edition.uuid, edition.cover_format)

    cover_hash, cover_format, cover_color = await cover_service.save_cover(cover_bytes, edition.uuid)
    if not cover_hash:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Could not process image")

    edition.cover_hash = cover_hash
    edition.cover_format = cover_format
    edition.cover_color = cover_color
    await db.commit()
    await db.refresh(edition)
    return BookRead.model_validate(edition)


@router.get("/{book_id}/cover/search")
async def search_covers(
    book_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Search all metadata providers for cover images for this book.

    Returns a list of {provider, url, thumbnail_url} objects for the UI
    to display as a cover picker grid.
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")

    stmt = select(Edition).where(Edition.id == book_id).options(*_edition_options())
    result = await db.execute(stmt)
    edition = result.unique().scalar_one_or_none()
    if not edition:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")

    work = edition.work
    from app.services.metadata_enrichment import enrichment_service
    author_names = [a.name for a in work.authors]
    file_ext = f".{edition.files[0].format}" if edition.files else None

    results = await enrichment_service.search_all_providers(
        work.title, author_names, edition.isbn, file_extension=file_ext
    )

    covers = []
    seen_urls = set()
    for r in results:
        url = r.get("cover_url")
        if url and url not in seen_urls:
            seen_urls.add(url)
            covers.append({
                "provider": r.get("_provider", "unknown"),
                "url": url,
            })

    return covers


class CoverUrlRequest(BaseModel):
    url: str


@router.post("/{book_id}/cover/from-url", response_model=BookRead)
async def set_cover_from_url(
    book_id: int,
    data: CoverUrlRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Set a book's cover by downloading from a URL."""
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")

    result = await db.execute(
        select(Edition).options(*_edition_options()).where(Edition.id == book_id)
    )
    edition = result.unique().scalar_one_or_none()
    if not edition:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")

    import httpx
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
            r = await client.get(data.url)
            r.raise_for_status()
            cover_bytes = r.content
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to download image: {exc}")

    if not cover_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty image response")

    from app.services.covers import cover_service
    if edition.cover_format:
        await cover_service.delete_cover(edition.uuid, edition.cover_format)

    cover_hash, cover_format, cover_color = await cover_service.save_cover(cover_bytes, edition.uuid)
    if not cover_hash:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Could not process image")

    edition.cover_hash = cover_hash
    edition.cover_format = cover_format
    edition.cover_color = cover_color
    await db.commit()
    await db.refresh(edition)
    return BookRead.model_validate(edition)


@router.get("/{book_id}/download/{file_id}")
async def download_book_file(
    book_id: int,
    file_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download a book file."""
    stmt = select(EditionFile).where(
        and_(EditionFile.id == file_id, EditionFile.edition_id == book_id)
    )
    result = await db.execute(stmt)
    edition_file = result.scalar_one_or_none()

    if not edition_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    edition = await db.get(Edition, edition_file.edition_id)
    if edition is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="File not found"
        )
    await assert_library_access(db, current_user, edition.library_id)

    from app.config import resolve_path
    from app.services.file_streaming import stream_file_response
    file_path = Path(resolve_path(edition_file.file_path))

    media_types = {
        "epub": "application/epub+zip",
        "kepub": "application/kepub+zip",
        "pdf": "application/pdf",
        "cbz": "application/vnd.comicbook+zip",
        "cbr": "application/vnd.comicbook-rar",
        "mobi": "application/x-mobipocket-ebook",
        "azw3": "application/vnd.amazon.ebook",
    }
    media_type = media_types.get(
        (edition_file.format or "").lower(), "application/octet-stream"
    )
    return stream_file_response(
        request,
        file_path,
        media_type=media_type,
        filename=edition_file.filename,
    )


@router.get("/enrichment/providers")
async def list_enrichment_providers(
    _current_user: User = Depends(get_current_user),
):
    """List available metadata enrichment providers and their status."""
    from app.services.metadata_enrichment import enrichment_service
    return enrichment_service.available_providers()


@router.get("/{book_id}/enrich/stream")
async def enrich_book_metadata_stream(
    book_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stream metadata enrichment results per-provider via Server-Sent Events."""
    import json as _json
    from starlette.responses import StreamingResponse

    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")

    stmt = select(Edition).where(Edition.id == book_id).options(*_edition_options())
    result = await db.execute(stmt)
    edition = result.unique().scalar_one_or_none()
    if not edition:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")

    work = edition.work
    from app.services.metadata_enrichment import enrichment_service
    author_names = [a.name for a in work.authors]
    file_ext = f".{edition.files[0].format}" if edition.files else None

    async def event_generator():
        merged: dict = {}
        async for provider_name, result, provider_status in enrichment_service.enrich_stream(
            work.title, author_names, edition.isbn, file_extension=file_ext
        ):
            event = {
                "provider": provider_name,
                "status": provider_status,
                "fields": list(result.keys()) if result else [],
                "has_cover": bool(result.get("cover_url")) if result else False,
                "has_description": bool(result.get("description")) if result else False,
                "title": result.get("title") if result else None,
            }
            if result:
                for key, val in result.items():
                    if key not in merged and val:
                        merged[key] = val
            yield f"data: {_json.dumps(event)}\n\n"

        # Final merged result
        yield f"data: {_json.dumps({'event': 'done', 'merged_fields': list(merged.keys()), 'total_providers': len(enrichment_service.available_providers())})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{book_id}/enrich/proposals")
async def get_enrichment_proposals(
    book_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return metadata results from all providers for side-by-side comparison."""
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")

    stmt = select(Edition).where(Edition.id == book_id).options(*_edition_options())
    result = await db.execute(stmt)
    edition = result.unique().scalar_one_or_none()
    if not edition:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")

    work = edition.work
    from app.services.metadata_enrichment import enrichment_service
    author_names = [a.name for a in work.authors]
    file_ext = f".{edition.files[0].format}" if edition.files else None

    proposals = await enrichment_service.search_all_providers(
        work.title, author_names, edition.isbn, file_extension=file_ext
    )

    # Sanitize: only return serializable fields
    safe_fields = {
        "title", "subtitle", "description", "authors", "tags", "isbn",
        "published_date", "publisher", "page_count", "language",
        "cover_url", "goodreads_rating", "goodreads_rating_count",
        "amazon_rating", "amazon_rating_count", "goodreads_id",
        "google_id", "hardcover_id", "asin", "doi", "awards",
        "content_warnings", "characters", "places", "_provider",
    }
    return [
        {k: v for k, v in p.items() if k in safe_fields and v}
        for p in proposals
    ]


class UrlExtractRequest(BaseModel):
    url: str


@router.post("/extract-from-url")
async def extract_metadata_from_url(
    data: UrlExtractRequest,
    current_user: User = Depends(get_current_user),
):
    """Extract Open Graph / Dublin Core metadata from a web page.

    Useful for previewing metadata before applying it to a book.
    Works with publisher pages, Goodreads, Amazon, etc.
    """
    from app.services.opengraph import extract_from_url
    return await extract_from_url(data.url)


@router.post("/{book_id}/enrich-from-url", response_model=BookRead)
async def enrich_book_from_url(
    book_id: int,
    data: UrlExtractRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Enrich a book's metadata from a web page URL (Open Graph extraction).

    Fills in empty fields only. Also downloads cover image if available.
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")

    from app.services.opengraph import extract_from_url
    from app.services.covers import cover_service

    stmt = select(Edition).where(Edition.id == book_id).options(*_edition_options())
    result = await db.execute(stmt)
    edition = result.unique().scalar_one_or_none()
    if not edition:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")

    work = edition.work
    meta = await extract_from_url(data.url)

    # Apply metadata to empty fields only
    if meta.get("title") and not work.title:
        work.title = meta["title"]
    if meta.get("description") and not work.description:
        work.description = meta["description"]
    if meta.get("isbn") and not edition.isbn:
        from app.utils.isbn import normalize
        isbn13, isbn10 = normalize(meta["isbn"])
        edition.isbn = isbn13
        edition.isbn_10 = isbn10
    if meta.get("publisher") and not edition.publisher:
        edition.publisher = meta["publisher"]
    if meta.get("language") and not edition.language:
        edition.language = meta["language"]
    if meta.get("published_date") and not edition.published_date:
        edition.published_date = meta["published_date"]

    # Add authors if none exist
    if meta.get("authors") and not work.authors:
        for aname in meta["authors"]:
            existing = await db.execute(select(Author).where(Author.name == aname))
            author = existing.scalar_one_or_none()
            if not author:
                author = Author(name=aname)
                db.add(author)
                await db.flush()
            work.authors.append(author)

    # Download cover if available and book has none
    if meta.get("image_url") and not edition.cover_hash:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                resp = await client.get(meta["image_url"])
                if resp.status_code == 200 and len(resp.content) > 1000:
                    cover_hash, cover_format, cover_color = await cover_service.save_cover(
                        resp.content, edition.uuid
                    )
                    if cover_hash:
                        edition.cover_hash = cover_hash
                        edition.cover_format = cover_format
                        edition.cover_color = cover_color
        except Exception:
            pass  # Cover download is non-critical

    await db.commit()

    # Re-fetch for response
    result = await db.execute(
        select(Edition).where(Edition.id == book_id).options(*_edition_options())
    )
    edition = result.unique().scalar_one()

    from app.services.search import search_service
    await search_service.index_work(db, work, [a.name for a in work.authors])
    await db.commit()

    return BookRead.model_validate(edition)


@router.post("/{book_id}/enrich", response_model=BookRead)
async def enrich_book_metadata(
    book_id: int,
    provider: Optional[str] = None,
    force: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Enrich book metadata from external providers.

    Pass ?provider=hardcover to use a specific provider.
    Pass ?force=true to overwrite existing fields (default: fill gaps only).
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    stmt = select(Edition).where(Edition.id == book_id).options(*_edition_options())
    result = await db.execute(stmt)
    edition = result.unique().scalar_one_or_none()
    if not edition:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")

    work = edition.work
    from app.services.metadata_enrichment import enrichment_service
    author_names = [a.name for a in work.authors]
    file_ext = f".{edition.files[0].format}" if edition.files else None

    if provider:
        enriched = await enrichment_service.search_provider(provider, work.title, author_names, edition.isbn)
    else:
        enriched = await enrichment_service.enrich(work.title, author_names, edition.isbn, file_extension=file_ext)

    if not enriched:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No enrichment data found")

    await _apply_enrichment(db, edition, work, enriched, force=force)

    from app.services.audit import log_action
    await log_action(db, "book.enrich", user_id=current_user.id,
                     entity_type="edition", entity_id=book_id,
                     detail=f"provider={provider or 'auto'}, fields={list(enriched.keys())[:10]}")
    await db.commit()
    await db.refresh(edition)

    from app.services.search import search_service
    await db.refresh(work, ["authors", "contributors"])
    await search_service.index_work(db, work, [a.name for a in work.authors])
    await db.commit()

    return BookRead.model_validate(edition)


@router.post("/{book_id}/extract-identifiers")
async def extract_book_identifiers(
    book_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Scan a book's file content for ISBN and DOI.

    Updates the edition's isbn/isbn_10 and the work's doi if found and currently empty.
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")

    from app.services.identifier_extraction import extract_identifiers_for_edition
    ids = await extract_identifiers_for_edition(book_id)

    return {
        "isbn_13": ids.get("isbn_13"),
        "isbn_10": ids.get("isbn_10"),
        "doi": ids.get("doi"),
        "isbn_source": ids.get("isbn_source"),
        "doi_source": ids.get("doi_source"),
    }


@router.get("/{book_id}/series-neighbors")
async def get_series_neighbors(
    book_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Get previous/next books in the same series for navigation."""
    from app.models.work import work_series

    stmt = select(Edition).where(Edition.id == book_id).options(*_edition_options())
    result = await db.execute(stmt)
    edition = result.unique().scalar_one_or_none()
    if not edition or not edition.work:
        return {"series": []}

    work = edition.work
    if not work.series:
        return {"series": []}

    neighbors = []
    for series in work.series:
        # Get all works in this series with their positions
        ws_stmt = (
            select(
                work_series.c.work_id,
                work_series.c.position,
                Work.title,
            )
            .join(Work, Work.id == work_series.c.work_id)
            .where(work_series.c.series_id == series.id)
            .order_by(work_series.c.position.asc().nulls_last(), Work.title.asc())
        )
        rows = (await db.execute(ws_stmt)).all()

        # Find current work's index
        current_idx = None
        entries = []
        for i, (wid, pos, title) in enumerate(rows):
            # Get edition ID for this work
            ed_result = await db.scalar(
                select(Edition.id).where(Edition.work_id == wid).limit(1)
            )
            entries.append({"work_id": wid, "edition_id": ed_result, "position": pos, "title": title})
            if wid == work.id:
                current_idx = i

        if current_idx is None:
            continue

        prev_book = entries[current_idx - 1] if current_idx > 0 else None
        next_book = entries[current_idx + 1] if current_idx < len(entries) - 1 else None

        neighbors.append({
            "series_id": series.id,
            "series_name": series.name,
            "current_position": entries[current_idx]["position"],
            "total": len(entries),
            "previous": {"id": prev_book["edition_id"], "title": prev_book["title"], "position": prev_book["position"]} if prev_book and prev_book["edition_id"] else None,
            "next": {"id": next_book["edition_id"], "title": next_book["title"], "position": next_book["position"]} if next_book and next_book["edition_id"] else None,
        })

    return {"series": neighbors}


class ReadingLevelUpdate(BaseModel):
    """Manual reading level update."""
    lexile: Optional[int] = None
    lexile_code: Optional[str] = None
    ar_level: Optional[float] = None
    ar_points: Optional[float] = None
    age_range: Optional[str] = None
    interest_level: Optional[str] = None


@router.patch("/{book_id}/reading-level")
async def update_reading_level(
    book_id: int,
    data: ReadingLevelUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Set reading level fields (Lexile, AR, age range, etc.) for a book."""
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")

    stmt = select(Edition).where(Edition.id == book_id).options(*_edition_options())
    result = await db.execute(stmt)
    edition = result.unique().scalar_one_or_none()
    if not edition:
        raise HTTPException(status_code=404, detail="Book not found")

    work = edition.work
    for field in ["lexile", "lexile_code", "ar_level", "ar_points", "age_range", "interest_level"]:
        val = getattr(data, field, None)
        if val is not None:
            setattr(work, field, val)

    await db.commit()
    return {"ok": True}


@router.post("/{book_id}/compute-reading-level")
async def compute_book_reading_level(
    book_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Compute Flesch-Kincaid grade level from book text content."""
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")

    stmt = select(Edition).where(Edition.id == book_id).options(*_edition_options())
    result = await db.execute(stmt)
    edition = result.unique().scalar_one_or_none()
    if not edition:
        raise HTTPException(status_code=404, detail="Book not found")

    from app.services.reading_level import compute_reading_level
    result = await compute_reading_level(edition.work_id)
    return result


@router.get("/{book_id}/files/{file_id}/manifest.json")
async def get_divina_manifest(
    book_id: int,
    file_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return a DiViNa WebPub Manifest for a comic file (Readium compatible)."""
    stmt = select(EditionFile).where(EditionFile.id == file_id, EditionFile.edition_id == book_id)
    result = await db.execute(stmt)
    edition_file = result.scalar_one_or_none()
    if not edition_file:
        raise HTTPException(status_code=404, detail="File not found")
    if edition_file.format.lower() not in ("cbz", "cbr"):
        raise HTTPException(status_code=400, detail="DiViNa manifests only for comic files")

    edition_result = await db.execute(
        select(Edition).where(Edition.id == book_id).options(*_edition_options())
    )
    edition = edition_result.unique().scalar_one_or_none()
    if not edition:
        raise HTTPException(status_code=404, detail="Book not found")
    await assert_library_access(db, current_user, edition.library_id)

    from app.services.divina import generate_divina_manifest
    scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.url.netloc)
    base_url = f"{scheme}://{host}"

    work = edition.work
    manifest = generate_divina_manifest(
        edition_id=book_id,
        file_id=file_id,
        file_path=edition_file.file_path,
        title=work.title if work else f"Edition {book_id}",
        authors=[a.name for a in work.authors] if work and work.authors else [],
        base_url=base_url,
        reading_direction=work.reading_direction or "ltr" if work else "ltr",
        page_count=work.page_count_comic if work else None,
    )
    if not manifest:
        raise HTTPException(status_code=404, detail="Could not generate manifest")

    return JSONResponse(
        content=manifest,
        media_type="application/divina+json",
    )


@router.get("/{book_id}/files/{file_id}/pages")
async def get_comic_page_count(
    book_id: int,
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the number of pages in a CBZ/CBR comic file."""
    stmt = select(EditionFile).where(EditionFile.id == file_id, EditionFile.edition_id == book_id)
    result = await db.execute(stmt)
    edition_file = result.scalar_one_or_none()
    if not edition_file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    edition = await db.get(Edition, edition_file.edition_id)
    if edition is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    await assert_library_access(db, current_user, edition.library_id)

    from app.config import resolve_path as _rp
    file_path = Path(_rp(edition_file.file_path))
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found on disk")

    fmt = (edition_file.format or "").lower()
    if fmt == "cbz":
        import zipfile
        with zipfile.ZipFile(file_path) as z:
            images = sorted(
                n for n in z.namelist()
                if n.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif"))
                and not n.startswith("__MACOSX")
            )
        return {"count": len(images), "format": fmt}
    raise HTTPException(status_code=400, detail=f"Unsupported comic format: {fmt}")


@router.get("/{book_id}/files/{file_id}/pages/{page_num}")
async def get_comic_page(
    book_id: int,
    file_id: int,
    page_num: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return a single page image from a CBZ comic file (0-indexed)."""
    stmt = select(EditionFile).where(EditionFile.id == file_id, EditionFile.edition_id == book_id)
    result = await db.execute(stmt)
    edition_file = result.scalar_one_or_none()
    if not edition_file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    edition = await db.get(Edition, edition_file.edition_id)
    if edition is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    await assert_library_access(db, current_user, edition.library_id)

    from app.config import resolve_path as _rp
    file_path = Path(_rp(edition_file.file_path))
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found on disk")

    fmt = (edition_file.format or "").lower()
    if fmt != "cbz":
        raise HTTPException(status_code=400, detail=f"Unsupported comic format: {fmt}")

    import io
    import zipfile
    from fastapi.responses import StreamingResponse

    with zipfile.ZipFile(file_path) as z:
        images = sorted(
            n for n in z.namelist()
            if n.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif"))
            and not n.startswith("__MACOSX")
        )
        if page_num < 0 or page_num >= len(images):
            raise HTTPException(status_code=404, detail="Page not found")
        image_data = z.read(images[page_num])
        name = images[page_num].lower()
        media_type = (
            "image/png" if name.endswith(".png")
            else "image/webp" if name.endswith(".webp")
            else "image/jpeg"
        )
    return StreamingResponse(io.BytesIO(image_data), media_type=media_type)


@router.post("/{book_id}/files/{file_id}/convert", response_model=BookRead)
async def convert_book_file(
    book_id: int,
    file_id: int,
    output_format: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Convert a book file to another format (pure Python, no external tools)."""
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    stmt = select(EditionFile).where(EditionFile.id == file_id, EditionFile.edition_id == book_id)
    result = await db.execute(stmt)
    edition_file = result.scalar_one_or_none()
    if not edition_file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    from app.services.conversion import conversion_service
    from app.config import resolve_path as _rp
    input_path = Path(_rp(edition_file.file_path))
    if not input_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found on disk")

    output_path = await conversion_service.convert_file(input_path, output_format)
    if not output_path:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Conversion failed")

    new_file = EditionFile(
        edition_id=book_id,
        filename=output_path.name,
        format=get_file_format(output_path),
        file_path=str(output_path),
        file_size=get_file_size(output_path),
        file_hash=calculate_file_hash(output_path),
    )
    db.add(new_file)
    await db.commit()

    stmt = select(Edition).where(Edition.id == book_id).options(*_edition_options())
    result = await db.execute(stmt)
    edition = result.unique().scalar_one_or_none()
    return BookRead.model_validate(edition)


from pydantic import BaseModel as PydanticBase


class SendBookRequest(PydanticBase):
    recipient: str  # e.g. mydevice@kindle.com
    file_id: Optional[int] = None  # defaults to first file


@router.post("/{book_id}/send")
async def send_book_to_device(
    book_id: int,
    data: SendBookRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Email a book file to a Kindle or other device via SMTP.

    Configure SMTP_HOST, SMTP_USER, SMTP_PASS, SMTP_FROM in .env to enable.
    """
    from app.services.email import EmailDeliveryError, is_configured, send_book_to_email

    if not is_configured():
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="SMTP delivery is not configured on this server.",
        )

    stmt = select(Edition).where(Edition.id == book_id).options(joinedload(Edition.work), joinedload(Edition.files))
    result = await db.execute(stmt)
    edition = result.unique().scalar_one_or_none()
    if not edition:
        raise HTTPException(status_code=404, detail="Book not found")

    if data.file_id:
        edition_file = next((f for f in edition.files if f.id == data.file_id), None)
    else:
        edition_file = edition.files[0] if edition.files else None

    if not edition_file:
        raise HTTPException(status_code=404, detail="No file available for this book")

    from app.config import resolve_path as _rp
    file_path = Path(_rp(edition_file.file_path))
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    try:
        await send_book_to_email(
            recipient=data.recipient,
            file_path=file_path,
            book_title=edition.title,
        )
    except EmailDeliveryError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return {"ok": True, "recipient": data.recipient, "filename": edition_file.filename}


@router.get("/{book_id}/shelves", response_model=list[ShelfRead])
async def get_book_shelves(
    book_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all static shelves that contain this book (for the current user)."""
    stmt = (
        select(Shelf)
        .join(ShelfBook, ShelfBook.shelf_id == Shelf.id)
        .join(Edition, Edition.work_id == ShelfBook.work_id)
        .where(
            Edition.id == book_id,
            Shelf.user_id == current_user.id,
            Shelf.is_smart == False,  # noqa: E712
        )
    )
    result = await db.execute(stmt)
    shelves = result.scalars().all()
    return [ShelfRead.model_validate(s) for s in shelves]


@router.get("/{book_id}/series-entries")
async def get_book_series_entries(
    book_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return series membership with position/volume/arc for a book."""
    edition = (await db.execute(select(Edition).where(Edition.id == book_id))).scalar_one_or_none()
    if not edition:
        raise HTTPException(status_code=404, detail="Book not found")
    rows = await db.execute(
        select(
            work_series.c.series_id,
            Series.name,
            work_series.c.position,
            work_series.c.volume,
            work_series.c.arc,
        )
        .join(Series, Series.id == work_series.c.series_id)
        .where(work_series.c.work_id == edition.work_id)
    )
    return [
        {"series_id": sid, "name": name, "position": pos, "volume": vol, "arc": arc}
        for sid, name, pos, vol, arc in rows
    ]


async def _apply_enrichment(
    db: AsyncSession,
    edition: "Edition",
    work: "Work",
    enriched: dict,
    force: bool = False,
) -> bool:
    """Apply enriched metadata dict to work+edition.

    Returns True if any field was changed.
    Only writes a field when it is currently empty, unless force=True.
    Respects locked_fields on both work and edition.
    """
    import json as _json
    _locked: set[str] = set()
    if edition.locked_fields:
        try:
            _locked |= set(_json.loads(edition.locked_fields))
        except Exception:
            pass
    if work.locked_fields:
        try:
            _locked |= set(_json.loads(work.locked_fields))
        except Exception:
            pass

    changed = False

    def _want(field: str, current) -> bool:
        """Return True if we should write this field."""
        if field in _locked:
            return False
        return force or not current

    # ── Work fields ───────────────────────────────────────────────────────────
    if enriched.get("subtitle") and _want("subtitle", work.subtitle):
        work.subtitle = enriched["subtitle"]
        changed = True
    if enriched.get("description") and _want("description", work.description):
        work.description = enriched["description"]
        changed = True
    if enriched.get("language") and _want("language", work.language):
        work.language = enriched["language"]
        changed = True
    if enriched.get("doi") and _want("doi", work.doi):
        work.doi = enriched["doi"]
        changed = True

    # ── Reading levels (Work-level) ──────────────────────────────────────────
    if enriched.get("lexile") and _want("lexile", work.lexile):
        work.lexile = enriched["lexile"]
        changed = True
    if enriched.get("lexile_code") and _want("lexile_code", work.lexile_code):
        work.lexile_code = enriched["lexile_code"]
        changed = True
    if enriched.get("ar_level") and _want("ar_level", work.ar_level):
        work.ar_level = enriched["ar_level"]
        changed = True
    if enriched.get("ar_points") and _want("ar_points", work.ar_points):
        work.ar_points = enriched["ar_points"]
        changed = True
    if enriched.get("age_range") and _want("age_range", work.age_range):
        work.age_range = enriched["age_range"]
        changed = True
    if enriched.get("interest_level") and _want("interest_level", work.interest_level):
        work.interest_level = enriched["interest_level"]
        changed = True

    # ── External IDs & ratings ──────────────────────────────────────────────
    if enriched.get("goodreads_id") and not work.goodreads_id:
        work.goodreads_id = enriched["goodreads_id"]
        changed = True
    if enriched.get("google_id") and not work.google_id:
        work.google_id = enriched["google_id"]
        changed = True
    if enriched.get("hardcover_id") and not work.hardcover_id:
        work.hardcover_id = enriched["hardcover_id"]
        changed = True
    if enriched.get("goodreads_rating") and not work.goodreads_rating:
        work.goodreads_rating = enriched["goodreads_rating"]
        work.goodreads_rating_count = enriched.get("goodreads_rating_count")
        changed = True
    if enriched.get("amazon_rating") and not work.amazon_rating:
        work.amazon_rating = enriched["amazon_rating"]
        work.amazon_rating_count = enriched.get("amazon_rating_count")
        changed = True
    if enriched.get("awards") and not work.awards:
        import json as _awards_json
        work.awards = _awards_json.dumps(enriched["awards"])
        changed = True

    # ── Edition fields ────────────────────────────────────────────────────────
    if enriched.get("isbn") and _want("isbn", edition.isbn):
        from app.utils.isbn import normalize as _normalize_isbn
        isbn13, isbn10 = _normalize_isbn(enriched["isbn"])
        edition.isbn = isbn13
        if isbn10 and not edition.isbn_10:
            edition.isbn_10 = isbn10
        changed = True
    if enriched.get("asin") and _want("asin", edition.asin):
        edition.asin = enriched["asin"]
        changed = True
    if enriched.get("published_date") and _want("published_date", edition.published_date):
        from datetime import datetime as _dt
        raw = str(enriched["published_date"])[:10]
        for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
            try:
                edition.published_date = _dt.strptime(raw[:len(fmt)], fmt)
                changed = True
                break
            except ValueError:
                continue
    if enriched.get("publisher") and _want("publisher", edition.publisher):
        edition.publisher = enriched["publisher"]
        changed = True
    if enriched.get("page_count") and _want("page_count", edition.page_count):
        try:
            edition.page_count = int(enriched["page_count"])
            changed = True
        except (ValueError, TypeError):
            pass

    # ── Work relationships ────────────────────────────────────────────────────
    if enriched.get("authors") and _want("authors", work.authors):
        work.authors = await _get_or_create(db, Author, "name", enriched["authors"])
        changed = True
    if enriched.get("tags") and _want("tags", work.tags):
        work.tags = await _get_or_create(db, Tag, "name", enriched["tags"])
        changed = True

    # ── StoryGraph fields ─────────────────────────────────────────────────────
    if enriched.get("content_warnings") and _want("content_warnings", work.content_warnings):
        cw = enriched["content_warnings"]
        work.content_warnings = _json.dumps(cw) if isinstance(cw, dict) else cw
        changed = True

    # ── LibraryThing CK fields (work-level JSON columns) ─────────────────────
    if enriched.get("characters") and _want("characters", work.characters):
        work.characters = _json.dumps(enriched["characters"])
        changed = True
    if enriched.get("places") and _want("places", work.places):
        work.places = _json.dumps(enriched["places"])
        changed = True
    if enriched.get("awards") and _want("awards", work.awards):
        work.awards = _json.dumps(enriched["awards"])
        changed = True
    if enriched.get("original_language") and _want("original_language", work.original_language):
        work.original_language = enriched["original_language"]
        changed = True
    if enriched.get("original_publication_year") and _want("original_publication_year", work.original_publication_year):
        work.original_publication_year = enriched["original_publication_year"]
        changed = True

    # ── Cover ─────────────────────────────────────────────────────────────────
    if enriched.get("cover_url") and _want("cover", edition.cover_hash):
        try:
            import httpx as _httpx
            from app.services.covers import cover_service
            async with _httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                resp = await client.get(enriched["cover_url"])
                if resp.status_code == 200 and resp.content:
                    cover_hash, cover_format, cover_color = await cover_service.save_cover(resp.content, edition.uuid)
                    if cover_hash:
                        edition.cover_hash = cover_hash
                        edition.cover_format = cover_format
                        edition.cover_color = cover_color
                        changed = True
        except Exception as exc:
            logger.warning("Failed to download cover from %s: %s", enriched.get("cover_url"), exc)

    return changed


async def _get_or_create(db: AsyncSession, model, field: str, names: list[str]) -> list:
    """Fetch or create model instances by name."""
    entities = []
    for name in names:
        name = name.strip()
        if not name:
            continue
        result = await db.execute(select(model).where(getattr(model, field) == name))
        entity = result.scalar_one_or_none()
        if entity is None:
            entity = model(**{field: name})
            db.add(entity)
            await db.flush()
        entities.append(entity)
    return entities


# ── Recommendations ────────────────────────────────────────────────────────────

class BookRecommendation(BaseModel):
    id: int
    title: str
    author: Optional[str] = None
    cover_hash: Optional[str] = None
    cover_format: Optional[str] = None
    score: int  # overlap count
    reasons: list[str] = []  # human-readable match reasons


@router.get("/{book_id}/recommendations", response_model=list[BookRecommendation])
async def get_recommendations(
    book_id: int,
    limit: int = Query(8, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return books similar to the given book based on shared authors, series, and tags.

    Inspired by Booklore's recommendation engine. Scores each candidate by the
    number of overlapping relationships (author = 2 pts, series = 3 pts, tag = 1 pt).
    """
    # Load the source edition with work relationships
    ed_result = await db.execute(
        select(Edition)
        .options(
            joinedload(Edition.work).options(
                joinedload(Work.authors),
                joinedload(Work.series),
                joinedload(Work.tags),
            )
        )
        .where(Edition.id == book_id)
    )
    edition = ed_result.unique().scalar_one_or_none()
    if not edition:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")

    work = edition.work
    author_ids = {a.id for a in work.authors}
    series_ids = {s.id for s in work.series}
    tag_ids = {t.id for t in work.tags}

    if not author_ids and not series_ids and not tag_ids:
        return []

    # Find candidate work IDs per relationship
    work_scores: dict[int, int] = {}

    async def _add(stmt_inner, points: int) -> None:
        r = await db.execute(stmt_inner)
        for row in r.mappings():
            wid = row["work_id"]
            if wid != work.id:
                work_scores[wid] = work_scores.get(wid, 0) + points

    if author_ids:
        await _add(
            select(work_authors.c.work_id).where(work_authors.c.author_id.in_(author_ids)),
            2,
        )
    if series_ids:
        await _add(
            select(work_series.c.work_id).where(work_series.c.series_id.in_(series_ids)),
            3,
        )
    if tag_ids:
        await _add(
            select(work_tags.c.work_id).where(work_tags.c.tag_id.in_(tag_ids)),
            1,
        )

    if not work_scores:
        return []

    # Sort by score desc, take top candidates
    top_work_ids = sorted(work_scores, key=lambda k: -work_scores[k])[:limit]

    # Find one edition per candidate work (prefer same library)
    cands_result = await db.execute(
        select(Edition)
        .options(
            joinedload(Edition.work).options(
                joinedload(Work.authors),
                joinedload(Work.series),
                joinedload(Work.tags),
            )
        )
        .where(Edition.work_id.in_(top_work_ids))
    )
    # Collect one edition per work_id (first encountered)
    cands: dict[int, Edition] = {}
    for e in cands_result.unique().scalars().all():
        if e.work_id not in cands:
            cands[e.work_id] = e

    def _reasons(cand_work: Work) -> list[str]:
        r: list[str] = []
        for a in cand_work.authors:
            if a.id in author_ids:
                r.append(f"By {a.name}")
        for s in cand_work.series:
            if s.id in series_ids:
                r.append(s.name)
        tag_matches = [t.name for t in cand_work.tags if t.id in tag_ids][:3]
        r.extend(tag_matches)
        return r

    return [
        BookRecommendation(
            id=cands[wid].id,
            title=cands[wid].work.title,
            author=cands[wid].work.authors[0].name if cands[wid].work.authors else None,
            cover_hash=cands[wid].cover_hash,
            cover_format=cands[wid].cover_format,
            score=work_scores[wid],
            reasons=_reasons(cands[wid].work),
        )
        for wid in top_work_ids
        if wid in cands
    ]
