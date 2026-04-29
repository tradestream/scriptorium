"""Ordered reading lists.

Distinct from ``Shelf`` (a flat user-curated bag) and ``Collection`` (a
flat or smart-filtered grouping). A reading list is an *ordered*
sequence with first-class next/previous navigation: arc-by-arc comic
runs, course curricula, "things I want to read this year in this
order", etc. Borrowed from Kavita / Komga where reading lists are a
separate entity from collections.

Schema:
  - ``ReadingList`` rows are per-user (``user_id`` FK), private to
    that user. No sharing yet — same convention as ``Shelf``.
  - ``ReadingListEntry`` rows hold the ordered sequence keyed by
    ``(reading_list_id, position)``. Position is a sparse integer so
    we can renumber on bulk reorder without touching every row.
  - Entries point at ``Edition`` (specific file/cover) rather than
    ``Work`` because a reading list can mix editions of the same work
    (e.g. "the unabridged version followed by the audiobook").
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class ReadingList(Base):
    """An ordered, user-owned sequence of editions to read in turn."""

    __tablename__ = "reading_lists"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # ``cover_work_id`` matches the Collection naming convention: pick a
    # representative work whose canonical edition supplies the thumbnail.
    cover_work_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("works.id"), nullable=True
    )
    # External provenance — set when the list came from a CBL import or
    # other external source. Free-form so future importers don't need a
    # schema migration each time.
    source: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    # ComicVine ID when imported from a CBL pointing at a specific arc.
    comicvine_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_pinned: Mapped[bool] = mapped_column(default=False)
    sync_to_kobo: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    entries: Mapped[list["ReadingListEntry"]] = relationship(
        "ReadingListEntry",
        back_populates="reading_list",
        cascade="all, delete-orphan",
        order_by="ReadingListEntry.position",
    )


class ReadingListEntry(Base):
    """One position in a reading list, pointing at a specific edition."""

    __tablename__ = "reading_list_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    reading_list_id: Mapped[int] = mapped_column(
        ForeignKey("reading_lists.id", ondelete="CASCADE"), index=True
    )
    edition_id: Mapped[int] = mapped_column(
        ForeignKey("editions.id", ondelete="CASCADE"), index=True
    )
    # Sparse integer; the API renumbers in steps of 10 on bulk reorder
    # so single insert / move ops can land between two existing rows
    # without rewriting the whole list.
    position: Mapped[int] = mapped_column(Integer)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    reading_list: Mapped["ReadingList"] = relationship(
        "ReadingList", back_populates="entries"
    )

    __table_args__ = (
        Index("ix_reading_list_entries_list_position", "reading_list_id", "position"),
    )
