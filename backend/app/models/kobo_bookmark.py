"""Kobo device bookmarks — raw data from KoboReader.sqlite Bookmark table.

Synced via Koblime-style push from device. Preserves original Kobo fields
for lossless round-tripping. Linked to Scriptorium annotations for display.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class KoboBookmark(Base):
    """A bookmark/highlight/annotation from a Kobo device."""

    __tablename__ = "kobo_bookmarks"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    edition_id: Mapped[Optional[int]] = mapped_column(ForeignKey("editions.id"), nullable=True, index=True)

    # Original Kobo fields (verbatim from KoboReader.sqlite Bookmark table)
    bookmark_id: Mapped[str] = mapped_column(String(255))  # Kobo UUID
    volume_id: Mapped[str] = mapped_column(String(512), index=True)  # ContentID
    text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Highlighted passage
    annotation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # User note
    start_container_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    start_container_child_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    start_offset: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    end_container_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    end_container_child_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    end_offset: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    extra_annotation_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    date_created: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    date_modified: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Sync metadata
    device_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    @property
    def bookmark_type(self) -> str:
        """Classify the bookmark: bookmark, highlight, or annotation."""
        if self.start_container_child_index == 0 and self.start_offset == 0 and not self.text:
            return "bookmark"
        if self.text and self.annotation:
            return "annotation"
        if self.text:
            return "highlight"
        return "bookmark"


class KoboContentMap(Base):
    """Maps Kobo VolumeID (ContentID) to Scriptorium editions."""

    __tablename__ = "kobo_content_map"

    id: Mapped[int] = mapped_column(primary_key=True)
    volume_id: Mapped[str] = mapped_column(String(512), unique=True, index=True)
    edition_id: Mapped[int] = mapped_column(ForeignKey("editions.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
