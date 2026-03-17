from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AuthorBase(BaseModel):
    """Author base schema."""

    name: str
    description: Optional[str] = None


class AuthorRead(AuthorBase):
    """Author read schema."""

    id: int
    photo_url: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class TagBase(BaseModel):
    """Tag base schema."""

    name: str


class TagRead(TagBase):
    """Tag read schema."""

    id: int
    model_config = ConfigDict(from_attributes=True)


class SeriesBase(BaseModel):
    """Series base schema."""

    name: str
    description: Optional[str] = None


class SeriesRead(SeriesBase):
    """Series read schema."""

    id: int
    model_config = ConfigDict(from_attributes=True)


class BookFileRead(BaseModel):
    """Book file read schema."""

    id: int
    filename: str
    format: str
    file_size: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class BookBase(BaseModel):
    """Book base schema."""

    title: str
    subtitle: Optional[str] = None
    description: Optional[str] = None
    isbn: Optional[str] = None
    language: Optional[str] = None
    published_date: Optional[datetime] = None
    publisher: Optional[str] = None

    @field_validator('isbn', mode='before')
    @classmethod
    def normalize_isbn(cls, v):
        if not v or not isinstance(v, str):
            return v
        from app.utils.isbn import normalize
        isbn13, _ = normalize(v)
        return isbn13


class BookCreate(BookBase):
    """Book create schema."""

    library_id: int
    physical_copy: bool = False
    binding: Optional[str] = None
    condition: Optional[str] = None
    purchase_price: Optional[float] = None
    purchase_date: Optional[datetime] = None
    purchase_from: Optional[str] = None
    location: Optional[str] = None
    location_id: Optional[int] = None
    author_ids: list[int] = Field(default_factory=list)
    tag_ids: list[int] = Field(default_factory=list)
    series_ids: list[int] = Field(default_factory=list)
    # Convenience: resolve authors/tags by name at creation time
    author_names: list[str] = Field(default_factory=list)
    tag_names: list[str] = Field(default_factory=list)


class BookUpdate(BaseModel):
    """Book update schema.

    Relationships can be set by ID (author_ids) or by name (author_names).
    Name-based fields create the entity if it doesn't exist.
    Providing both for the same relationship is an error.
    """

    title: Optional[str] = None
    subtitle: Optional[str] = None
    description: Optional[str] = None
    isbn: Optional[str] = None
    language: Optional[str] = None
    published_date: Optional[datetime] = None
    publisher: Optional[str] = None

    @field_validator('isbn', mode='before')
    @classmethod
    def normalize_isbn(cls, v):
        if not v or not isinstance(v, str):
            return v
        from app.utils.isbn import normalize
        isbn13, _ = normalize(v)
        return isbn13
    # By ID (for clients that already know IDs)
    author_ids: Optional[list[int]] = None
    tag_ids: Optional[list[int]] = None
    series_ids: Optional[list[int]] = None
    # By name (create-or-get; easier for metadata editors)
    author_names: Optional[list[str]] = None
    tag_names: Optional[list[str]] = None
    series_names: Optional[list[str]] = None
    # Contributors by role
    translator_names: Optional[list[str]] = None
    editor_names: Optional[list[str]] = None
    illustrator_names: Optional[list[str]] = None
    colorist_names: Optional[list[str]] = None
    physical_copy: Optional[bool] = None
    binding: Optional[str] = None
    condition: Optional[str] = None
    purchase_price: Optional[float] = None
    purchase_date: Optional[datetime] = None
    purchase_from: Optional[str] = None
    location: Optional[str] = None
    location_id: Optional[int] = None


class BookRead(BookBase):
    """Book read schema."""

    id: int
    uuid: str
    library_id: int
    isbn_10: Optional[str] = None
    asin: Optional[str] = None
    binding: Optional[str] = None
    condition: Optional[str] = None
    purchase_price: Optional[float] = None
    purchase_date: Optional[datetime] = None
    purchase_from: Optional[str] = None
    location: Optional[str] = None
    location_id: Optional[int] = None
    location_name: Optional[str] = None
    cover_hash: Optional[str] = None
    cover_format: Optional[str] = None
    cover_color: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    authors: list[AuthorRead] = Field(default_factory=list)
    tags: list[TagRead] = Field(default_factory=list)
    series: list[SeriesRead] = Field(default_factory=list)
    files: list[BookFileRead] = Field(default_factory=list)
    translators: list[str] = Field(default_factory=list)
    editors: list[str] = Field(default_factory=list)
    illustrators: list[str] = Field(default_factory=list)
    colorists: list[str] = Field(default_factory=list)
    locked_fields: list[str] = []
    esoteric_enabled: bool = False
    physical_copy: bool = False
    abs_item_id: Optional[str] = None
    doi: Optional[str] = None
    goodreads_id: Optional[str] = None
    google_id: Optional[str] = None
    hardcover_id: Optional[str] = None
    goodreads_rating: Optional[float] = None
    goodreads_rating_count: Optional[int] = None
    amazon_rating: Optional[float] = None
    amazon_rating_count: Optional[int] = None
    lexile: Optional[int] = None
    lexile_code: Optional[str] = None
    ar_level: Optional[float] = None
    ar_points: Optional[float] = None
    flesch_kincaid_grade: Optional[float] = None
    age_range: Optional[str] = None
    interest_level: Optional[str] = None
    content_warnings: Optional[dict] = None

    @field_validator('content_warnings', mode='before')
    @classmethod
    def parse_content_warnings(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            import json
            return json.loads(v)
        return v

    @field_validator('locked_fields', mode='before')
    @classmethod
    def parse_locked_fields(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            import json
            return json.loads(v)
        return v

    model_config = ConfigDict(from_attributes=True)


class BookListResponse(BaseModel):
    """Book list response with pagination."""

    items: list[BookRead]
    total: int
    skip: int
    limit: int
