"""Schemas for Work (abstract creative work) and related objects."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.book import AuthorRead, SeriesRead, TagRead


class WorkContributorRead(BaseModel):
    id: int
    name: str
    role: str
    model_config = ConfigDict(from_attributes=True)


class WorkBase(BaseModel):
    title: str
    subtitle: Optional[str] = None
    description: Optional[str] = None
    language: Optional[str] = None
    original_language: Optional[str] = None
    original_publication_year: Optional[int] = None
    esoteric_enabled: bool = False


class WorkCreate(WorkBase):
    author_names: list[str] = Field(default_factory=list)
    tag_names: list[str] = Field(default_factory=list)
    # Series by name with optional position
    series_entries: list[dict] = Field(default_factory=list)
    editor_names: list[str] = Field(default_factory=list)
    illustrator_names: list[str] = Field(default_factory=list)
    colorist_names: list[str] = Field(default_factory=list)


class WorkUpdate(BaseModel):
    title: Optional[str] = None
    subtitle: Optional[str] = None
    description: Optional[str] = None
    language: Optional[str] = None
    original_language: Optional[str] = None
    original_publication_year: Optional[int] = None
    esoteric_enabled: Optional[bool] = None
    # Common Knowledge fields
    characters: Optional[list[str]] = None
    places: Optional[list[str]] = None
    awards: Optional[list[dict]] = None
    # Set relationships by name (create-or-get)
    author_names: Optional[list[str]] = None
    tag_names: Optional[list[str]] = None
    series_names: Optional[list[str]] = None
    editor_names: Optional[list[str]] = None
    illustrator_names: Optional[list[str]] = None
    colorist_names: Optional[list[str]] = None
    locked_fields: Optional[list[str]] = None


class WorkRead(WorkBase):
    id: int
    uuid: str
    locked_fields: list[str] = []
    characters: list[str] = []
    places: list[str] = []
    awards: list[dict] = []
    created_at: datetime
    updated_at: datetime
    authors: list[AuthorRead] = Field(default_factory=list)
    tags: list[TagRead] = Field(default_factory=list)
    series: list[SeriesRead] = Field(default_factory=list)
    editors: list[str] = Field(default_factory=list)
    illustrators: list[str] = Field(default_factory=list)
    colorists: list[str] = Field(default_factory=list)
    # Editions are loaded separately to avoid N+1 on list views
    edition_count: int = 0

    @field_validator("locked_fields", "characters", "places", mode="before")
    @classmethod
    def parse_json_str_list(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            import json
            return json.loads(v)
        return v

    @field_validator("awards", mode="before")
    @classmethod
    def parse_awards(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            import json
            return json.loads(v)
        return v

    model_config = ConfigDict(from_attributes=True)


class WorkListResponse(BaseModel):
    items: list[WorkRead]
    total: int
    skip: int
    limit: int
