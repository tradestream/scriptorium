from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class Annotation(Base):
    """A highlight, note, or bookmark on an edition."""

    __tablename__ = "annotations"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    edition_id: Mapped[int] = mapped_column(ForeignKey("editions.id"), index=True)
    # Type: highlight | note | bookmark
    type: Mapped[str] = mapped_column(String(20), index=True)
    # Text content of note / highlighted passage
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # EPUB CFI or "page:N" for PDF/CBZ
    location: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    # Chapter or section label for display
    chapter: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # Highlight color: yellow | green | blue | pink | purple
    color: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    # JSON arrays for thematic tagging and cross-referencing
    tags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    related_refs: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Attribution — for notes quoting external commentators
    commentator: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_spoiler: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
