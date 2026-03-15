"""Device management API."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.database import get_db
from app.models import User
from app.models.progress import Device

router = APIRouter(prefix="/devices", tags=["devices"])


@router.get("")
async def list_devices(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all reading devices registered to the current user."""
    result = await db.execute(
        select(Device)
        .where(Device.user_id == current_user.id)
        .order_by(Device.last_synced.desc().nullslast())
    )
    devices = result.scalars().all()
    return [
        {
            "id": d.id,
            "name": d.name,
            "device_type": d.device_type,
            "device_model": d.device_model,
            "last_synced": d.last_synced.isoformat() if d.last_synced else None,
            "created_at": d.created_at.isoformat(),
        }
        for d in devices
    ]


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(
    device_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a device (admin users can remove any device; regular users only their own)."""
    result = await db.execute(
        select(Device).where(Device.id == device_id, Device.user_id == current_user.id)
    )
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    await db.delete(device)
    await db.commit()
