"""Editions API — CRUD for specific copies of a Work, plus UserEdition and Loan management."""

import hashlib
import logging
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Edition, EditionContributor, EditionFile, Loan, User, UserEdition, Work
from app.schemas.edition import (
    EditionCreate, EditionRead, EditionUpdate, EditionWithWorkRead,
    LoanCreate, LoanRead, LoanUpdate,
    UserEditionRead, UserEditionUpdate,
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
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.config import get_settings
    edition = await _get_edition_or_404(edition_id, db)
    await _assert_accessible(edition, current_user, db)

    if not edition.cover_hash or not edition.cover_format:
        raise HTTPException(status_code=404, detail="No cover")

    settings = get_settings()
    cover_path = Path(settings.COVERS_PATH) / f"{edition.uuid}.{edition.cover_format}"
    if not cover_path.exists():
        raise HTTPException(status_code=404, detail="Cover file not found")

    return FileResponse(str(cover_path), media_type=f"image/{edition.cover_format}")


# ── File download ─────────────────────────────────────────────────────────────

@router.get("/{edition_id}/download/{file_id}")
async def download_edition_file(
    edition_id: int,
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    edition = await _get_edition_or_404(edition_id, db)
    await _assert_accessible(edition, current_user, db)

    ef = next((f for f in edition.files if f.id == file_id), None)
    if ef is None:
        raise HTTPException(status_code=404, detail="File not found")

    file_path = Path(ef.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not on disk")

    return FileResponse(
        str(file_path),
        filename=ef.filename,
        media_type="application/octet-stream",
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
    ef.file_hash = _hash_file(resolved)
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

    try:
        old_hash = ef.file_hash
        ef.file_hash = _hash_file(resolved)
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
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── UserEdition (reading status) ──────────────────────────────────────────────

@router.get("/{edition_id}/user-edition", response_model=Optional[UserEditionRead])
async def get_user_edition(
    edition_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the current user's reading relationship with this edition, or null."""
    result = await db.execute(
        select(UserEdition).where(
            UserEdition.edition_id == edition_id,
            UserEdition.user_id == current_user.id,
        )
    )
    ue = result.scalar_one_or_none()
    return UserEditionRead.model_validate(ue) if ue else None


@router.put("/{edition_id}/user-edition", response_model=UserEditionRead)
async def upsert_user_edition(
    edition_id: int,
    body: UserEditionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create or update the current user's reading state for this edition."""
    result = await db.execute(
        select(UserEdition).where(
            UserEdition.edition_id == edition_id,
            UserEdition.user_id == current_user.id,
        )
    )
    ue = result.scalar_one_or_none()
    if ue is None:
        ue = UserEdition(user_id=current_user.id, edition_id=edition_id)
        db.add(ue)

    for field in ("status", "current_page", "total_pages", "percentage",
                  "rating", "review", "started_at", "completed_at", "last_opened"):
        val = getattr(body, field, None)
        if val is not None:
            setattr(ue, field, val)

    # Auto-set started_at on first transition to "reading"
    if body.status == "reading" and ue.started_at is None:
        ue.started_at = datetime.utcnow()
    # Auto-set completed_at
    if body.status == "completed" and ue.completed_at is None:
        ue.completed_at = datetime.utcnow()

    await db.commit()
    await db.refresh(ue)
    return UserEditionRead.model_validate(ue)


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
