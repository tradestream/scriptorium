from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ShelfBase(BaseModel):
    """Shelf base schema."""

    name: str
    description: Optional[str] = None


class ShelfCreate(ShelfBase):
    """Shelf create schema."""

    is_smart: bool = False
    smart_filter: Optional[str] = None
    sync_to_kobo: bool = False


class ShelfUpdate(BaseModel):
    """Shelf update schema."""

    name: Optional[str] = None
    description: Optional[str] = None
    is_smart: Optional[bool] = None
    smart_filter: Optional[str] = None
    sync_to_kobo: Optional[bool] = None


class ShelfBookAdd(BaseModel):
    """Add book to shelf schema."""

    book_id: int


class ShelfRead(ShelfBase):
    """Shelf read schema."""

    id: int
    user_id: int
    is_smart: bool = False
    smart_filter: Optional[str] = None
    sync_to_kobo: bool = False
    created_at: datetime
    updated_at: datetime
    book_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class IngestLogRead(BaseModel):
    id: int
    filename: str
    status: str
    book_id: Optional[int] = None
    error_message: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
