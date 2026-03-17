from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.schemas.book import BookRead


class SmartFilter(BaseModel):
    """Filter rules for smart collections."""
    library_id: Optional[int] = None
    author: Optional[str] = None       # partial match
    tag: Optional[str] = None           # exact match
    series: Optional[str] = None        # partial match
    format: Optional[str] = None        # file format (epub, pdf, etc.)
    language: Optional[str] = None
    status: Optional[str] = None        # reading status
    has_isbn: Optional[bool] = None
    physical_copy: Optional[bool] = None
    binding: Optional[str] = None
    condition: Optional[str] = None
    min_rating: Optional[int] = None    # 1-5


class CollectionCreate(BaseModel):
    name: str
    description: Optional[str] = None
    cover_book_id: Optional[int] = None
    is_smart: bool = False
    is_pinned: bool = False
    smart_filter: Optional[SmartFilter] = None


class CollectionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    cover_book_id: Optional[int] = None
    is_smart: Optional[bool] = None
    is_pinned: Optional[bool] = None
    smart_filter: Optional[SmartFilter] = None


class CollectionRead(BaseModel):
    id: int
    user_id: int
    name: str
    description: Optional[str] = None
    cover_book_id: Optional[int] = None
    is_smart: bool = False
    is_pinned: bool = False
    smart_filter: Optional[dict] = None
    created_at: datetime
    updated_at: datetime
    book_count: int = 0
    model_config = ConfigDict(from_attributes=True)


class CollectionDetail(CollectionRead):
    """Full collection with ordered book entries."""
    books: list[BookRead] = []


class CollectionBookAdd(BaseModel):
    book_id: int
    position: Optional[int] = None
