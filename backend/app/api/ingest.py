import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models import User
from app.schemas.shelf import IngestLogRead
from app.services.ingest import ingest_service
from app.services.scanner import BOOK_EXTENSIONS
from app.utils.files import safe_child

from .auth import get_current_user

router = APIRouter(prefix="/ingest")


@router.get("/status")
async def get_ingest_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get ingest pipeline status."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can view ingest status",
        )

    status = await ingest_service.get_ingest_status()
    return status


@router.post("/trigger")
async def trigger_ingest(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually trigger ingest scan."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can trigger ingest",
        )

    await ingest_service.trigger_scan()

    return {
        "status": "queued",
        "message": "Ingest scan has been queued",
    }


@router.get("/history")
async def get_ingest_history(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get ingest history."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can view ingest history",
        )

    history = await ingest_service.get_history(skip=skip, limit=limit)
    return {
        "items": [IngestLogRead.model_validate(item) for item in history["items"]],
        "total": history["total"],
        "skip": history["skip"],
        "limit": history["limit"],
    }


@router.post("/upload")
async def upload_book_file(
    file: UploadFile = File(...),
    library_id: Optional[int] = Form(None),
    current_user: User = Depends(get_current_user),
):
    """Upload a book file via browser. Saves to the ingest directory for processing.

    Supports: EPUB, PDF, CBZ, CBR, MOBI, AZW, AZW3, FB2, DJVU.
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")

    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename")

    ext = Path(file.filename).suffix.lower()
    if ext not in BOOK_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format: {ext}. Supported: {', '.join(sorted(BOOK_EXTENSIONS))}",
        )

    settings = get_settings()
    ingest_path = Path(settings.INGEST_PATH)
    ingest_path.mkdir(parents=True, exist_ok=True)

    try:
        dest = safe_child(ingest_path, file.filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Avoid overwriting
    if dest.exists():
        stem, suffix = dest.stem, dest.suffix
        for n in range(2, 100):
            candidate = dest.with_name(f"{stem} ({n}){suffix}")
            if not candidate.exists():
                dest = candidate
                break

    # Stream the upload to disk so a hostile client can't pin arbitrary
    # gigabytes in process memory before the format sniff below runs.
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Verify the uploaded bytes actually match the advertised extension. The
    # extension check above is just a routing hint; without a content sniff,
    # an attacker can upload e.g. a CBR renamed to .epub and have the EPUB
    # extractor parse RAR bytes (or a renamed XHTML file pulled into the
    # web reader). Reject mismatches and remove the bad file.
    from app.services.metadata import detect_format_from_content

    ext_fmt = ext.lstrip(".")
    sniffed = detect_format_from_content(dest)
    # Accept the upload if either the sniffer agrees with the extension, or
    # the sniffer can't make a call (e.g. no signature for .azw — leave the
    # extension-trusted ingest path to handle those formats).
    if sniffed is not None and sniffed != ext_fmt and not (
        ext_fmt in {"azw", "azw3", "mobi"} and sniffed in {"azw", "azw3", "mobi"}
    ):
        try:
            dest.unlink()
        except OSError:
            pass
        raise HTTPException(
            status_code=400,
            detail=f"File contents are {sniffed!r} but filename claims {ext_fmt!r}",
        )

    return {"filename": dest.name, "size": dest.stat().st_size, "status": "queued"}
