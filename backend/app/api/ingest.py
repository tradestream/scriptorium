from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.schemas.shelf import IngestLogRead
from app.services.ingest import ingest_service

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
