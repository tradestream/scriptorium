from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.schemas.book import BookRead


class ReadingListCreate(BaseModel):
    name: str
    description: Optional[str] = None
    cover_work_id: Optional[int] = None
    is_pinned: bool = False
    sync_to_kobo: bool = False


class ReadingListUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    cover_work_id: Optional[int] = None
    is_pinned: Optional[bool] = None
    sync_to_kobo: Optional[bool] = None


class ReadingListEntryRead(BaseModel):
    id: int
    position: int
    notes: Optional[str] = None
    book: BookRead
    model_config = ConfigDict(from_attributes=True)


class ReadingListEntryAdd(BaseModel):
    book_id: int
    position: Optional[int] = None
    notes: Optional[str] = None


class ReadingListEntryReorder(BaseModel):
    """Bulk-reorder payload — caller sends the full ordered list of
    entry ids; the server renumbers ``position`` in steps of 10."""
    entry_ids: list[int]


class ReadingListRead(BaseModel):
    id: int
    user_id: int
    name: str
    description: Optional[str] = None
    cover_work_id: Optional[int] = None
    source: Optional[str] = None
    comicvine_id: Optional[str] = None
    is_pinned: bool = False
    sync_to_kobo: bool = False
    created_at: datetime
    updated_at: datetime
    entry_count: int = 0
    model_config = ConfigDict(from_attributes=True)


class ReadingListDetail(ReadingListRead):
    """Full reading list with ordered entries."""
    entries: list[ReadingListEntryRead] = []
