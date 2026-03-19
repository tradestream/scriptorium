from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class Collection(Base):
    """A thematic grouping of works.

    Can be manual (curated list) or smart (auto-populated by filter rules).
    Smart filter is a JSON object with optional keys:
    - library_id: int
    - author: str (partial match)
    - tag: str (exact match)
    - series: str (partial match)
    - format: str (file format)
    - language: str
    - status: str (reading status: want_to_read, reading, completed, abandoned)
    - has_isbn: bool
    - physical_copy: bool
    - binding: str
    - condition: str
    - min_rating: int (1-5)
    """

    __tablename__ = "collections"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_smart: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    smart_filter: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    sync_to_kobo: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    source: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # "kobo", null=web
    # Optional: pin a work whose cover represents this collection
    cover_work_id: Mapped[Optional[int]] = mapped_column(ForeignKey("works.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    entries: Mapped[list["CollectionBook"]] = relationship(
        "CollectionBook",
        back_populates="collection",
        cascade="all, delete-orphan",
        order_by="CollectionBook.position",
    )


class CollectionBook(Base):
    """A work entry in a collection."""

    __tablename__ = "collection_books"

    id: Mapped[int] = mapped_column(primary_key=True)
    collection_id: Mapped[int] = mapped_column(ForeignKey("collections.id"), index=True)
    work_id: Mapped[int] = mapped_column(ForeignKey("works.id"), nullable=False, index=True)
    position: Mapped[int] = mapped_column(default=0)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    collection: Mapped["Collection"] = relationship("Collection", back_populates="entries")
