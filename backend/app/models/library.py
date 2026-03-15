from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class LibraryAccess(Base):
    """Per-user access control for a library.

    If a library has NO entries here it is world-readable (all authenticated users).
    When at least one entry exists, only the listed users (plus admins) can see it.
    """

    __tablename__ = "library_access"

    id: Mapped[int] = mapped_column(primary_key=True)
    library_id: Mapped[int] = mapped_column(ForeignKey("libraries.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    # 'read' = read-only, 'write' = can manage books
    access_level: Mapped[str] = mapped_column(String(20), default="read")
    granted_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())


class Library(Base):
    """Library model for organizing collections."""

    __tablename__ = "libraries"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    path: Mapped[str] = mapped_column(String(512), unique=True)
    is_active: Mapped[bool] = mapped_column(default=True, index=True)
    is_hidden: Mapped[bool] = mapped_column(default=False, index=True)  # Hidden from dashboard/suggestions, still in sidebar
    sort_order: Mapped[int] = mapped_column(default=0)
    last_scanned: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    naming_pattern: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    editions: Mapped[list["Edition"]] = relationship("Edition", back_populates="library", cascade="all, delete-orphan")
