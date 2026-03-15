from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class DeviceBase(BaseModel):
    """Device base schema."""

    name: str
    device_type: str


class DeviceCreate(DeviceBase):
    """Device create schema."""

    pass


class DeviceRead(DeviceBase):
    """Device read schema."""

    id: int
    last_synced: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class ReadProgressBase(BaseModel):
    """Read progress base schema."""

    current_page: int = 0
    total_pages: Optional[int] = None
    percentage: float = 0.0
    status: str = "reading"


class ReadProgressUpdate(BaseModel):
    """Read progress update schema."""

    current_page: Optional[int] = None
    total_pages: Optional[int] = None
    percentage: Optional[float] = None
    status: Optional[str] = None


class ReadProgressRead(ReadProgressBase):
    """Read progress read schema."""

    id: int
    user_id: int
    book_id: int
    device_id: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    last_opened: datetime
    created_at: datetime

    class Config:
        from_attributes = True
