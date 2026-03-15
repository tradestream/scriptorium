from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class Shelf(Base):
    """Shelf model for organizing works into collections."""

    __tablename__ = "shelves"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    is_smart: Mapped[bool] = mapped_column(default=False)
    smart_filter: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    works: Mapped[list["Work"]] = relationship(
        "Work", secondary="shelf_books", back_populates="shelves"
    )


class ShelfBook(Base):
    """Shelf work association with position."""

    __tablename__ = "shelf_books"

    id: Mapped[int] = mapped_column(primary_key=True)
    shelf_id: Mapped[int] = mapped_column(ForeignKey("shelves.id"))
    work_id: Mapped[int] = mapped_column(ForeignKey("works.id"), index=True)
    position: Mapped[int] = mapped_column(default=0)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
