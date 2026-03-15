from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class Collection(Base):
    """A thematic grouping of works (e.g. a shared universe, a publisher series)."""

    __tablename__ = "collections"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
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
