"""Schemas for Edition, EditionFile, per-user reading state, and Loan.

UserEditionRead/Update are wire-shape preserved across the unified-
progress migration: the underlying tables changed (ReadingState +
EditionPosition replace UserEdition), but these schemas continue to
describe the per-(user, edition) reading-state payload the frontend
already speaks.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.work import WorkRead


class EditionFileRead(BaseModel):
    id: int
    filename: str
    format: str
    file_size: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class EditionContributorRead(BaseModel):
    id: int
    name: str
    role: str
    model_config = ConfigDict(from_attributes=True)


# ── Edition ───────────────────────────────────────────────────────────────────

class EditionBase(BaseModel):
    isbn: Optional[str] = None
    publisher: Optional[str] = None
    published_date: Optional[datetime] = None
    language: Optional[str] = None
    format: Optional[str] = None
    page_count: Optional[int] = None
    physical_copy: bool = False

    @field_validator('isbn', mode='before')
    @classmethod
    def normalize_isbn(cls, v):
        if not v or not isinstance(v, str):
            return v
        from app.utils.isbn import normalize
        isbn13, _ = normalize(v)
        return isbn13


class EditionCreate(EditionBase):
    work_id: int
    library_id: int
    translator_names: list[str] = Field(default_factory=list)


class EditionUpdate(BaseModel):
    isbn: Optional[str] = None
    publisher: Optional[str] = None
    published_date: Optional[datetime] = None
    language: Optional[str] = None
    format: Optional[str] = None
    page_count: Optional[int] = None
    physical_copy: Optional[bool] = None
    location: Optional[str] = None
    translator_names: Optional[list[str]] = None
    locked_fields: Optional[list[str]] = None

    @field_validator('isbn', mode='before')
    @classmethod
    def normalize_isbn(cls, v):
        if not v or not isinstance(v, str):
            return v
        from app.utils.isbn import normalize
        isbn13, _ = normalize(v)
        return isbn13


class EditionRead(EditionBase):
    id: int
    uuid: str
    work_id: int
    library_id: int
    isbn_10: Optional[str] = None
    asin: Optional[str] = None
    location: Optional[str] = None
    cover_hash: Optional[str] = None
    cover_format: Optional[str] = None
    abs_item_id: Optional[str] = None
    locked_fields: list[str] = []
    created_at: datetime
    updated_at: datetime
    files: list[EditionFileRead] = Field(default_factory=list)
    translators: list[str] = Field(default_factory=list)

    @field_validator("locked_fields", mode="before")
    @classmethod
    def parse_locked_fields(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            import json
            return json.loads(v)
        return v

    model_config = ConfigDict(from_attributes=True)


class EditionWithWorkRead(EditionRead):
    """Edition response that embeds its Work — used in detail views."""
    work: Optional[WorkRead] = None


# ── UserEdition ───────────────────────────────────────────────────────────────

class UserEditionUpdate(BaseModel):
    status: Optional[str] = None          # want_to_read | reading | completed | abandoned
    current_page: Optional[int] = None
    total_pages: Optional[int] = None
    percentage: Optional[float] = None
    rating: Optional[int] = None           # 1–5
    review: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    last_opened: Optional[datetime] = None


class UserEditionRead(BaseModel):
    id: int
    user_id: int
    edition_id: int
    status: str
    current_page: int
    total_pages: Optional[int] = None
    percentage: float
    rating: Optional[int] = None
    review: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    last_opened: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ── Loan ──────────────────────────────────────────────────────────────────────

class LoanCreate(BaseModel):
    loaned_to_user_id: Optional[int] = None
    loaned_to_name: Optional[str] = None
    loaned_at: Optional[datetime] = None
    due_back: Optional[datetime] = None
    notes: Optional[str] = None


class LoanUpdate(BaseModel):
    due_back: Optional[datetime] = None
    returned_at: Optional[datetime] = None
    notes: Optional[str] = None


class LoanRead(BaseModel):
    id: int
    edition_id: int
    loaned_to_user_id: Optional[int] = None
    loaned_to_name: Optional[str] = None
    loaned_at: datetime
    due_back: Optional[datetime] = None
    returned_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
