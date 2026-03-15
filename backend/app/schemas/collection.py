from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.schemas.book import BookRead


class CollectionCreate(BaseModel):
    name: str
    description: Optional[str] = None
    cover_book_id: Optional[int] = None


class CollectionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    cover_book_id: Optional[int] = None


class CollectionRead(BaseModel):
    id: int
    user_id: int
    name: str
    description: Optional[str] = None
    cover_book_id: Optional[int] = None
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
