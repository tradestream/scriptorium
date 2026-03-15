"""KOReader Progress Sync (kosync-compatible API).

The KOReader Progress Sync plugin is configured with:
  Custom sync server: https://your-server/api/ko

Endpoints (kosync protocol):
  POST /api/ko/users/create       — register (maps to existing accounts)
  GET  /api/ko/users/auth         — authenticate
  PUT  /api/ko/syncs/progress     — update reading progress
  GET  /api/ko/syncs/progress/{document}  — get reading progress

Authentication uses HTTP Basic Auth (username:password).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.progress import KOReaderProgress
from app.models.user import User

router = APIRouter(prefix="/api/ko", tags=["koreader"])

_security = HTTPBasic(realm="Scriptorium", auto_error=False)


# ── Auth ───────────────────────────────────────────────────────────────────────

async def _auth(
    credentials: Optional[HTTPBasicCredentials] = Depends(_security),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": 'Basic realm="Scriptorium"'},
        )
    result = await db.execute(
        select(User).where(User.username == credentials.username, User.is_active.is_(True))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            headers={"WWW-Authenticate": 'Basic realm="Scriptorium"'})
    from app.services.auth import verify_password
    if not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            headers={"WWW-Authenticate": 'Basic realm="Scriptorium"'})
    return user


# ── Schemas ────────────────────────────────────────────────────────────────────

class ProgressUpdate(BaseModel):
    document: str
    progress: str
    percentage: float
    device: Optional[str] = None
    device_id: Optional[str] = None


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/users/create")
async def koreader_create_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """KOReader user registration.

    KOReader calls this on first setup. We don't allow self-registration
    via this endpoint — users must be created in the Scriptorium web UI.
    Return a 200 with the username if the account already exists so
    KOReader falls through to login.
    """
    body = await request.json()
    username = body.get("username", "")
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user:
        return {"username": username}
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Registration via KOReader is not supported. Create your account in the Scriptorium web UI.",
    )


@router.get("/users/auth")
async def koreader_auth(user: User = Depends(_auth)):
    """KOReader authentication check. Returns 200 if credentials are valid."""
    return {"username": user.username}


@router.put("/syncs/progress")
async def koreader_update_progress(
    body: ProgressUpdate,
    user: User = Depends(_auth),
    db: AsyncSession = Depends(get_db),
):
    """Update reading progress from KOReader."""
    now = datetime.now(timezone.utc)

    stmt = select(KOReaderProgress).where(
        and_(
            KOReaderProgress.user_id == user.id,
            KOReaderProgress.document == body.document,
        )
    )
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()

    if record:
        record.progress = body.progress
        record.percentage = body.percentage
        record.device = body.device
        record.device_id = body.device_id
        record.updated_at = now
    else:
        record = KOReaderProgress(
            user_id=user.id,
            document=body.document,
            progress=body.progress,
            percentage=body.percentage,
            device=body.device,
            device_id=body.device_id,
            updated_at=now,
        )
        db.add(record)

    await db.commit()

    return {
        "document": record.document,
        "timestamp": int(now.timestamp()),
    }


@router.get("/syncs/progress/{document}")
async def koreader_get_progress(
    document: str,
    user: User = Depends(_auth),
    db: AsyncSession = Depends(get_db),
):
    """Get reading progress for a document."""
    stmt = select(KOReaderProgress).where(
        and_(
            KOReaderProgress.user_id == user.id,
            KOReaderProgress.document == document,
        )
    )
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No progress found")

    return {
        "document": record.document,
        "progress": record.progress,
        "percentage": record.percentage,
        "device": record.device,
        "device_id": record.device_id,
        "timestamp": int(record.updated_at.timestamp()),
    }
