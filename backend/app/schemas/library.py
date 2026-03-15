from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class LibraryBase(BaseModel):
    """Library base schema."""

    name: str
    description: Optional[str] = None
    path: str


class LibraryCreate(LibraryBase):
    """Library create schema."""

    pass


class LibraryUpdate(BaseModel):
    """Library update schema."""

    name: Optional[str] = None
    description: Optional[str] = None
    path: Optional[str] = None
    is_active: Optional[bool] = None
    is_hidden: Optional[bool] = None
    naming_pattern: Optional[str] = None


class LibraryRead(LibraryBase):
    """Library read schema."""

    id: int
    is_active: bool
    is_hidden: bool = False
    sort_order: int = 0
    last_scanned: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    book_count: int = 0
    naming_pattern: Optional[str] = None

    class Config:
        from_attributes = True
