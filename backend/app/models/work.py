"""Work model — the abstract creative work (title, authors, series, etc.)."""

from datetime import datetime
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Table, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


# ── Association tables ────────────────────────────────────────────────────────

work_authors = Table(
    "work_authors",
    Base.metadata,
    Column("work_id", Integer, ForeignKey("works.id"), primary_key=True),
    Column("author_id", Integer, ForeignKey("authors.id"), primary_key=True),
)

work_tags = Table(
    "work_tags",
    Base.metadata,
    Column("work_id", Integer, ForeignKey("works.id"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id"), primary_key=True),
)

work_series = Table(
    "work_series",
    Base.metadata,
    Column("work_id", Integer, ForeignKey("works.id"), primary_key=True),
    Column("series_id", Integer, ForeignKey("series.id"), primary_key=True),
    Column("position", Float, nullable=True),
    Column("volume", String(100), nullable=True),
    Column("arc", String(255), nullable=True),
)


class Work(Base):
    """The abstract creative work — what the book *is*, independent of any
    specific physical or digital copy.

    Edition-specific data (ISBN, publisher, cover, files) lives on Edition.
    """

    __tablename__ = "works"

    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    subtitle: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Primary language of the original work
    language: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    # Language the work was first written in (may differ from library edition language)
    original_language: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    # Year the work was first published in any language/edition
    original_publication_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # JSON arrays for Common Knowledge fields
    characters: Mapped[Optional[str]] = mapped_column(Text, nullable=True)   # ["Hamlet", "Ophelia", ...]
    places: Mapped[Optional[str]] = mapped_column(Text, nullable=True)        # ["Elsinore", "Denmark", ...]
    awards: Mapped[Optional[str]] = mapped_column(Text, nullable=True)        # [{"name": "Hugo", "year": 1966, "category": "Best Novel"}, ...]
    content_warnings: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # {"graphic": [...], "moderate": [...], "minor": [...]}
    doi: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    # JSON array of field names locked from enrichment edits
    locked_fields: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default=None)
    esoteric_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    # ── Relationships ─────────────────────────────────────────────────────────
    authors: Mapped[list["Author"]] = relationship(
        "Author", secondary="work_authors", back_populates="works"
    )
    tags: Mapped[list["Tag"]] = relationship(
        "Tag", secondary="work_tags", back_populates="works"
    )
    series: Mapped[list["Series"]] = relationship(
        "Series", secondary="work_series", back_populates="works"
    )
    editions: Mapped[list["Edition"]] = relationship(
        "Edition", back_populates="work", cascade="all, delete-orphan"
    )
    contributors: Mapped[list["WorkContributor"]] = relationship(
        "WorkContributor", back_populates="work", cascade="all, delete-orphan"
    )
    shelves: Mapped[list["Shelf"]] = relationship(
        "Shelf", secondary="shelf_books", back_populates="works"
    )
    analyses: Mapped[list["BookAnalysis"]] = relationship(
        "BookAnalysis", back_populates="work", cascade="all, delete-orphan"
    )
    computational_analyses: Mapped[list["ComputationalAnalysis"]] = relationship(
        "ComputationalAnalysis", back_populates="work", cascade="all, delete-orphan"
    )
    prompt_configs: Mapped[list["BookPromptConfig"]] = relationship(
        "BookPromptConfig", back_populates="work", cascade="all, delete-orphan"
    )

    @property
    def editors(self) -> list[str]:
        return [c.name for c in self.contributors if c.role == "editor"]

    @property
    def illustrators(self) -> list[str]:
        return [c.name for c in self.contributors if c.role == "illustrator"]

    @property
    def colorists(self) -> list[str]:
        return [c.name for c in self.contributors if c.role == "colorist"]


class WorkContributor(Base):
    """Work-level contributor (editor, illustrator, colorist)."""

    __tablename__ = "work_contributors"

    id: Mapped[int] = mapped_column(primary_key=True)
    work_id: Mapped[int] = mapped_column(ForeignKey("works.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(50), index=True)  # editor | illustrator | colorist

    work: Mapped["Work"] = relationship("Work", back_populates="contributors")
