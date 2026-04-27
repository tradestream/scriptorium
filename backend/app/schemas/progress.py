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


# ReadProgress* schemas were retired in step 4 of the unified-progress
# migration. The replacement surface lives on the inline ProgressUpdate
# Pydantic model in api/progress.py and the UserEditionRead/Update
# schemas in schemas/edition.py.
