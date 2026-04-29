from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


class LibraryBase(BaseModel):
    """Library base schema."""

    name: str
    description: Optional[str] = None
    path: str


class LibraryCreate(LibraryBase):
    """Library create schema."""

    exclude_patterns: Optional[list[str]] = None


class LibraryUpdate(BaseModel):
    """Library update schema."""

    name: Optional[str] = None
    description: Optional[str] = None
    path: Optional[str] = None
    is_active: Optional[bool] = None
    is_hidden: Optional[bool] = None
    naming_pattern: Optional[str] = None
    # ``None`` means "no change" on update; pass ``[]`` to clear back to
    # defaults-only.
    exclude_patterns: Optional[list[str]] = None


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
    exclude_patterns: Optional[list[str]] = None

    @field_validator("exclude_patterns", mode="before")
    @classmethod
    def _decode_patterns(cls, v):
        """The model stores patterns as a JSON-encoded text column;
        decode to a real list for the response."""
        if v in (None, "", []):
            return None if v is None else v
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            import json as _json
            try:
                parsed = _json.loads(v)
                return parsed if isinstance(parsed, list) else None
            except (TypeError, ValueError):
                return None
        return None

    class Config:
        from_attributes = True


class ScanResult(BaseModel):
    """Scan summary returned to the admin UI."""

    added: int = 0
    skipped: int = 0
    excluded: int = 0
    errors: list[str] = []
