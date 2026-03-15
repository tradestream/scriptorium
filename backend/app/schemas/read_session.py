from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ReadSessionCreate(BaseModel):
    book_id: int
    started_at: datetime
    finished_at: Optional[datetime] = None
    rating: Optional[int] = None  # 1–5
    notes: Optional[str] = None


class ReadSessionUpdate(BaseModel):
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    rating: Optional[int] = None
    notes: Optional[str] = None


class ReadSessionRead(BaseModel):
    id: int
    user_id: int
    book_id: int
    started_at: datetime
    finished_at: Optional[datetime] = None
    rating: Optional[int] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
