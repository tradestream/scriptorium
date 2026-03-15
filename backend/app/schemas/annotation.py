import json
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


def _parse_json_list(v: object) -> Optional[list[str]]:
    if v is None:
        return None
    if isinstance(v, list):
        return v
    if isinstance(v, str):
        try:
            parsed = json.loads(v)
            return parsed if isinstance(parsed, list) else [str(parsed)]
        except Exception:
            return [s.strip() for s in v.split(",") if s.strip()]
    return None


class AnnotationCreate(BaseModel):
    book_id: int
    file_id: Optional[int] = None
    type: str  # highlight | note | bookmark
    content: Optional[str] = None
    location: Optional[str] = None
    chapter: Optional[str] = None
    color: Optional[str] = None
    tags: Optional[list[str]] = None
    related_refs: Optional[list[str]] = None
    commentator: Optional[str] = None
    source: Optional[str] = None


class AnnotationUpdate(BaseModel):
    content: Optional[str] = None
    color: Optional[str] = None
    chapter: Optional[str] = None
    tags: Optional[list[str]] = None
    related_refs: Optional[list[str]] = None
    commentator: Optional[str] = None
    source: Optional[str] = None


class AnnotationRead(BaseModel):
    id: int
    user_id: int
    book_id: int
    file_id: Optional[int] = None
    type: str
    content: Optional[str] = None
    location: Optional[str] = None
    chapter: Optional[str] = None
    color: Optional[str] = None
    tags: Optional[list[str]] = None
    related_refs: Optional[list[str]] = None
    commentator: Optional[str] = None
    source: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

    @field_validator("tags", "related_refs", mode="before")
    @classmethod
    def _coerce_json_list(cls, v: object) -> Optional[list[str]]:
        return _parse_json_list(v)


class AnnotationWithBook(AnnotationRead):
    """AnnotationRead extended with book metadata for cross-book views."""
    book_title: Optional[str] = None
    book_author: Optional[str] = None
