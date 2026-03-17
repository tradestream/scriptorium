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

    dest = ingest_path / file.filename
    # Avoid overwriting
    if dest.exists():
        stem, suffix = dest.stem, dest.suffix
        for n in range(2, 100):
            candidate = dest.with_name(f"{stem} ({n}){suffix}")
            if not candidate.exists():
                dest = candidate
                break

    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    return {"filename": dest.name, "size": dest.stat().st_size, "status": "queued"}
