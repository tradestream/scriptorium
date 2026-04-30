"""Editions API — CRUD for specific copies of a Work, per-user reading state, and Loan management."""

import hashlib
import logging
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Edition, EditionContributor, EditionFile, Loan, User, Work
from app.schemas.edition import (
    EditionCreate,
    EditionRead,
    EditionUpdate,
    EditionWithWorkRead,
    LoanCreate,
    LoanRead,
    LoanUpdate,
    UserEditionRead,
    UserEditionUpdate,
)
from app.schemas.work import WorkRead

from .auth import get_accessible_library_ids, get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/editions")


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_edition_or_404(
    edition_id: int, db: AsyncSession, *, with_work: bool = False
) -> Edition:
    opts = [selectinload(Edition.files), selectinload(Edition.contributors)]
    if with_work:
        opts.append(
            selectinload(Edition.work).options(
                selectinload(Work.authors),
                selectinload(Work.tags),
                selectinload(Work.series),
                selectinload(Work.contributors),
            )
        )
    result = await db.execute(
        select(Edition).where(Edition.id == edition_id).options(*opts)
    )
    edition = result.scalar_one_or_none()
    if edition is None:
        raise HTTPException(status_code=404, detail="Edition not found")
    return edition


async def _assert_accessible(edition: Edition, current_user: User, db: AsyncSession) -> None:
    accessible = await get_accessible_library_ids(db, current_user)
    if accessible is not None and edition.library_id not in accessible:
        raise HTTPException(status_code=403, detail="Access denied")


# ── Edition CRUD ──────────────────────────────────────────────────────────────

@router.get("/{edition_id}", response_model=EditionWithWorkRead)
async def get_edition(
    edition_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    edition = await _get_edition_or_404(edition_id, db, with_work=True)
    await _assert_accessible(edition, current_user, db)
    resp = EditionWithWorkRead.model_validate(edition)
    if edition.work:
        resp.work = WorkRead.model_validate(edition.work)
    return resp


@router.post("", response_model=EditionRead, status_code=status.HTTP_201_CREATED)
async def create_edition(
    body: EditionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify the work exists
    work = await db.get(Work, body.work_id)
    if work is None:
        raise HTTPException(status_code=404, detail="Work not found")

    edition = Edition(
        uuid=str(uuid.uuid4()),
        work_id=body.work_id,
        library_id=body.library_id,
        isbn=body.isbn,
        publisher=body.publisher,
        published_date=body.published_date,
        language=body.language,
        format=body.format,
        page_count=body.page_count,
        physical_copy=body.physical_copy,
    )
    db.add(edition)
    await db.flush()

    for name in body.translator_names:
        if name.strip():
            db.add(EditionContributor(edition_id=edition.id, name=name.strip(), role="translator"))

    await db.commit()
    edition = await _get_edition_or_404(edition.id, db)
    return EditionRead.model_validate(edition)


@router.put("/{edition_id}", response_model=EditionRead)
async def update_edition(
    edition_id: int,
    body: EditionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    edition = await _get_edition_or_404(edition_id, db)
    await _assert_accessible(edition, current_user, db)

    for field in ("isbn", "publisher", "published_date", "language", "format", "page_count", "physical_copy"):
        val = getattr(body, field, None)
        if val is not None:
            setattr(edition, field, val)

    if body.locked_fields is not None:
        import json
        edition.locked_fields = json.dumps(body.locked_fields)

    if body.translator_names is not None:
        edition.contributors = []
        for name in body.translator_names:
            if name.strip():
                edition.contributors.append(
                    EditionContributor(edition_id=edition.id, name=name.strip(), role="translator")
                )

    await db.commit()
    edition = await _get_edition_or_404(edition_id, db)
    return EditionRead.model_validate(edition)


@router.delete("/{edition_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_edition(
    edition_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin only")
    edition = await _get_edition_or_404(edition_id, db)
    await db.delete(edition)
    await db.commit()


# ── Cover ─────────────────────────────────────────────────────────────────────

@router.get("/{edition_id}/cover")
async def get_edition_cover(
    edition_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.config import get_settings
    from app.services.file_streaming import stream_file_response
    edition = await _get_edition_or_404(edition_id, db)
    await _assert_accessible(edition, current_user, db)

    if not edition.cover_hash or not edition.cover_format:
        raise HTTPException(status_code=404, detail="No cover")

    settings = get_settings()
    cover_path = Path(settings.COVERS_PATH) / f"{edition.uuid}.{edition.cover_format}"
    media_type = (
        f"image/{edition.cover_format}" if edition.cover_format != "jpg" else "image/jpeg"
    )
    return stream_file_response(
        request,
        cover_path,
        media_type=media_type,
        cache_control="private, max-age=300",
        etag_salt=edition.cover_hash,
    )


# ── File download ─────────────────────────────────────────────────────────────

@router.get("/{edition_id}/download/{file_id}")
async def download_edition_file(
    edition_id: int,
    file_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.config import resolve_path
    from app.services.file_streaming import stream_file_response

    edition = await _get_edition_or_404(edition_id, db)
    await _assert_accessible(edition, current_user, db)

    ef = next((f for f in edition.files if f.id == file_id), None)
    if ef is None:
        raise HTTPException(status_code=404, detail="File not found")

    file_path = Path(resolve_path(ef.file_path))

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
        (ef.format or "").lower(), "application/octet-stream"
    )
    return stream_file_response(
        request,
        file_path,
        media_type=media_type,
        filename=ef.filename,
    )


# ── File replacement ─────────────────────────────────────────────────────────

def _require_admin(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin only")
    return current_user


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


@router.put("/{edition_id}/files/{file_id}/replace")
async def replace_edition_file(
    edition_id: int,
    file_id: int,
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(_require_admin),
):
    """Replace an edition's file with a new upload.

    Updates the file on disk, recalculates the hash, clears kepub and
    markdown caches so Kobo sync picks up the new version.
    """
    from app.config import resolve_path
    from app.services.markdown import markdown_path_for

    edition = await _get_edition_or_404(edition_id, db)
    ef = next((f for f in edition.files if f.id == file_id), None)
    if ef is None:
        raise HTTPException(status_code=404, detail="File not found")

    resolved = Path(resolve_path(ef.file_path))
    if not resolved.parent.exists():
        raise HTTPException(status_code=500, detail="Library directory not found")

    # Write new file to disk
    tmp_path = resolved.with_suffix(".tmp")
    try:
        with open(tmp_path, "wb") as out:
            while chunk := await file.read(8192):
                out.write(chunk)
        shutil.move(str(tmp_path), str(resolved))
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise

    # Update file metadata
    new_hash = _hash_file(resolved)
    dup = await db.execute(
        select(EditionFile).where(EditionFile.file_hash == new_hash, EditionFile.id != ef.id)
    )
    existing = dup.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Another file already has this hash (file_id={existing.id}, edition_id={existing.edition_id}). Delete the duplicate first.",
        )
    ef.file_hash = new_hash
    ef.file_size = resolved.stat().st_size
    if file.filename:
        ef.filename = file.filename

    # Clear kepub cache
    if ef.kepub_path:
        kepub_resolved = Path(resolve_path(ef.kepub_path))
        kepub_resolved.unlink(missing_ok=True)
        ef.kepub_path = None
        ef.kepub_hash = None

    # Clear markdown cache
    md_path = markdown_path_for(edition.uuid)
    if md_path.parent.exists():
        md_path.unlink(missing_ok=True)

    await db.commit()

    return {
        "file_id": ef.id,
        "edition_id": edition_id,
        "file_hash": ef.file_hash,
        "file_size": ef.file_size,
        "status": "replaced",
    }


@router.post("/{edition_id}/files/{file_id}/rehash")
async def rehash_edition_file(
    edition_id: int,
    file_id: int,
    clear_caches: bool = Query(True, description="Also clear kepub and markdown caches"),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(_require_admin),
):
    """Recalculate a file's hash from disk.

    Useful after replacing a file outside the application (e.g. manual copy).
    Clears kepub and markdown caches by default so they regenerate.
    """
    from app.config import resolve_path
    from app.services.markdown import markdown_path_for

    edition = await _get_edition_or_404(edition_id, db)
    ef = next((f for f in edition.files if f.id == file_id), None)
    if ef is None:
        raise HTTPException(status_code=404, detail="File not found")

    resolved = Path(resolve_path(ef.file_path))
    if not resolved.exists():
        raise HTTPException(status_code=404, detail=f"File not on disk: {resolved}")

    old_hash = ef.file_hash
    new_hash = _hash_file(resolved)

    # Check for duplicate hash (unique constraint on file_hash)
    if new_hash != old_hash:
        dup = await db.execute(
            select(EditionFile).where(EditionFile.file_hash == new_hash, EditionFile.id != ef.id)
        )
        existing = dup.scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Another file already has this hash (file_id={existing.id}, edition_id={existing.edition_id}). Delete the duplicate first.",
            )

    ef.file_hash = new_hash
    ef.file_size = resolved.stat().st_size

    if clear_caches:
        if ef.kepub_path:
            kepub_resolved = Path(resolve_path(ef.kepub_path))
            kepub_resolved.unlink(missing_ok=True)
            ef.kepub_path = None
            ef.kepub_hash = None
        md_path = markdown_path_for(edition.uuid)
        if md_path.parent.exists():
            md_path.unlink(missing_ok=True)

    await db.commit()

    return {
        "file_id": ef.id,
        "edition_id": edition_id,
        "old_hash": old_hash,
        "new_hash": ef.file_hash,
        "file_size": ef.file_size,
        "changed": old_hash != ef.file_hash,
    }


# ── User reading state (unified) ──────────────────────────────────────────────
#
# These endpoints preserve the legacy /editions/{id}/user-edition surface for
# the frontend, but now read from ReadingState (work-level lifecycle) +
# EditionPosition (per-edition cursor) and write through the unified
# write_progress helper.

@router.get("/{edition_id}/user-edition", response_model=Optional[UserEditionRead])
async def get_user_edition(
    edition_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the current user's reading state for this edition, or null."""
    from app.models.reading import EditionPosition, ReadingState

    edition = await db.get(Edition, edition_id)
    if edition is None:
        return None

    rs = (
        await db.execute(
            select(ReadingState).where(
                ReadingState.user_id == current_user.id,
                ReadingState.work_id == edition.work_id,
            )
        )
    ).scalar_one_or_none()
    ep = (
        await db.execute(
            select(EditionPosition).where(
                EditionPosition.user_id == current_user.id,
                EditionPosition.edition_id == edition_id,
            )
        )
    ).scalar_one_or_none()

    if rs is None and ep is None:
        return None

    pct = (ep.current_pct if ep else 0.0) * 100.0
    total_pages = ep.total_pages if ep else None
    current_page = int(round((pct / 100.0) * total_pages)) if total_pages else 0
    return UserEditionRead.model_validate({
        "id": rs.id if rs else 0,
        "user_id": current_user.id,
        "edition_id": edition_id,
        "status": rs.status if rs else "want_to_read",
        "current_page": current_page,
        "total_pages": total_pages,
        "percentage": pct,
        "rating": rs.rating if rs else None,
        "review": rs.review if rs else None,
        "started_at": rs.started_at if rs else None,
        "completed_at": rs.completed_at if rs else None,
        "last_opened": rs.last_opened if rs else None,
        "created_at": rs.created_at if rs else datetime.utcnow(),
        "updated_at": rs.updated_at if rs else datetime.utcnow(),
    })


@router.put("/{edition_id}/user-edition", response_model=UserEditionRead)
async def upsert_user_edition(
    edition_id: int,
    body: UserEditionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create or update the current user's reading state for this edition.

    Routes through the unified write_progress helper. Status / rating /
    review / lifecycle timestamps land on ReadingState; pct / total_pages
    land on EditionPosition. The legacy ``current_page`` field is treated
    as a derived display value: if provided alongside total_pages, we
    convert it to a pct.
    """
    from app.models.progress import Device
    from app.models.reading import EditionPosition
    from app.services.unified_progress import write_progress

    edition = await db.get(Edition, edition_id)
    if edition is None:
        raise HTTPException(status_code=404, detail="Edition not found")

    # Find or create a "web" device for this user — the same one
    # api/progress.py uses for unified writes.
    device = (
        await db.execute(
            select(Device).where(
                Device.user_id == current_user.id, Device.device_type == "web"
            )
        )
    ).scalar_one_or_none()
    if device is None:
        device = Device(
            user_id=current_user.id, name="Web Browser", device_type="web"
        )
        db.add(device)
        await db.flush()

    # Reuse existing cursor data if the body doesn't include a position.
    ep = (
        await db.execute(
            select(EditionPosition).where(
                EditionPosition.user_id == current_user.id,
                EditionPosition.edition_id == edition_id,
            )
        )
    ).scalar_one_or_none()

    incoming_pct = body.percentage if body.percentage is not None else None
    if incoming_pct is None and body.current_page is not None and body.total_pages:
        incoming_pct = (body.current_page / max(1, body.total_pages)) * 100.0

    cursor_pct = (incoming_pct / 100.0) if incoming_pct is not None else (
        ep.current_pct if ep else 0.0
    )
    cursor_format = ep.current_format if (ep and ep.current_format) else "percent"
    cursor_value = ep.current_value if (ep and ep.current_value) else str(round(cursor_pct * 100, 4))

    await write_progress(
        db,
        user_id=current_user.id,
        edition=edition,
        cursor_format=cursor_format,
        cursor_value=cursor_value,
        cursor_pct=cursor_pct,
        device_id=device.id,
        total_pages=body.total_pages,
        status_hint=body.status if body.status in ("completed", "abandoned", "reading") else None,
        rating=body.rating,
        review=body.review,
    )
    await db.commit()

    # Return the fresh shape via the GET handler logic — keeps response
    # consistent with frontend expectations.
    return await get_user_edition(edition_id=edition_id, db=db, current_user=current_user)


# ── Loans ─────────────────────────────────────────────────────────────────────

@router.get("/{edition_id}/loans", response_model=list[LoanRead])
async def list_edition_loans(
    edition_id: int,
    active_only: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    edition = await _get_edition_or_404(edition_id, db)
    await _assert_accessible(edition, current_user, db)

    stmt = select(Loan).where(Loan.edition_id == edition_id)
    if active_only:
        stmt = stmt.where(Loan.returned_at.is_(None))
    result = await db.execute(stmt)
    return [LoanRead.model_validate(loan) for loan in result.scalars().all()]


@router.post("/{edition_id}/loans", response_model=LoanRead, status_code=status.HTTP_201_CREATED)
async def create_loan(
    edition_id: int,
    body: LoanCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    edition = await _get_edition_or_404(edition_id, db)
    await _assert_accessible(edition, current_user, db)

    if not body.loaned_to_user_id and not body.loaned_to_name:
        raise HTTPException(status_code=422, detail="Provide loaned_to_user_id or loaned_to_name")

    loan = Loan(
        edition_id=edition_id,
        loaned_to_user_id=body.loaned_to_user_id,
        loaned_to_name=body.loaned_to_name,
        loaned_at=body.loaned_at or datetime.utcnow(),
        due_back=body.due_back,
        notes=body.notes,
    )
    db.add(loan)
    await db.commit()
    await db.refresh(loan)
    return LoanRead.model_validate(loan)


@router.patch("/{edition_id}/loans/{loan_id}", response_model=LoanRead)
async def update_loan(
    edition_id: int,
    loan_id: int,
    body: LoanUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Loan).where(Loan.id == loan_id, Loan.edition_id == edition_id)
    )
    loan = result.scalar_one_or_none()
    if loan is None:
        raise HTTPException(status_code=404, detail="Loan not found")

    if body.due_back is not None:
        loan.due_back = body.due_back
    if body.returned_at is not None:
        loan.returned_at = body.returned_at
    if body.notes is not None:
        loan.notes = body.notes

    await db.commit()
    await db.refresh(loan)
    return LoanRead.model_validate(loan)
