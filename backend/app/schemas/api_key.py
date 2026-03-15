from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ApiKeyCreate(BaseModel):
    name: str


class ApiKeyRead(BaseModel):
    id: int
    name: str
    prefix: str
    last_used_at: Optional[datetime] = None
    created_at: datetime
    is_active: bool
    model_config = ConfigDict(from_attributes=True)


class ApiKeyCreated(ApiKeyRead):
    """Returned once at creation time — includes the full key value."""
    key: str
