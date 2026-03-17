"""Hierarchical location model for tracking where physical books are stored.

Locations form a tree: House > Room > Bookcase > Shelf.
Each edition can optionally belong to one location.
Inspired by Homebox's self-referencing location model.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class Location(Base):
    """A physical location in a hierarchy (e.g., House > Living Room > Bookcase)."""

    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    parent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("locations.id"), nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    # Self-referencing tree
    parent: Mapped[Optional["Location"]] = relationship(
        "Location", remote_side="Location.id", back_populates="children"
    )
    children: Mapped[list["Location"]] = relationship(
        "Location", back_populates="parent", cascade="all, delete-orphan"
    )

    # Editions at this location
    editions: Mapped[list["Edition"]] = relationship(
        "Edition", back_populates="location_ref", foreign_keys="Edition.location_id"
    )

    @property
    def tree_path(self) -> str:
        """Build breadcrumb string: 'House > Living Room > Bookcase'."""
        parts = [self.name]
        current = self.parent
        while current:
            parts.append(current.name)
            current = current.parent
        parts.reverse()
        return " > ".join(parts)
