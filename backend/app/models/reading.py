"""Unified reading-progress schema.

Three tables that together replace the four overlapping legacy tables
(`ReadProgress`, `KoboBookState`, `UserEdition`, and the
`UserEdition`-side of `_sync_to_user_edition`):

- ``ReadingState``  — work-level lifecycle: status, rating, review,
  re-read counters, total reading time, timestamps. Survives format
  changes (EPUB ↔ audiobook of the same Work share a row).
- ``EditionPosition`` — per-edition canonical cursor + furthest-read
  watermark. The cursor is a tagged-union so each format keeps its
  native fidelity (web reader CFI, Kobo span, audio time_ms, page).
- ``DevicePosition`` — per-(user, edition, device) last-known native
  position. Powers "last read on Winston's Clara" UX and survives
  even when another device has overwritten ``EditionPosition``.

Design and decisions: see ``personal/design/unified_progress_schema.md``.
This file is a no-functional-change introduction — the legacy tables
remain authoritative until the backfill migration (0067) and read-path
switch land.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


# Status constants used by ReadingState. Mirrors what the legacy
# UserEdition.status field used; left as bare strings here (rather than
# an Enum column) for SQLite friendliness and to make backfill from the
# existing string columns mechanical.
STATUS_WANT_TO_READ = "want_to_read"
STATUS_READING = "reading"
STATUS_COMPLETED = "completed"
STATUS_ABANDONED = "abandoned"

# Cursor format discriminators for EditionPosition / DevicePosition.
# Open set — adding a new client (audiobook player, native mobile) is
# additive: define a new constant, write its adapter, no migration.
FORMAT_CFI = "cfi"                  # web reader (epubjs)
FORMAT_KOBO_SPAN = "kobo_span"      # Kobo Nickel; value = "chapter_href#span_id"
FORMAT_AUDIO_SECONDS = "audio_seconds"  # audiobook playhead
FORMAT_PAGE = "page"                # PDF / fixed-layout
FORMAT_PERCENT = "percent"          # opaque fallback (e.g. KOReader)


class ReadingState(Base):
    """Work-level lifecycle state.

    One row per (user, work). The cheap join target for library views,
    "currently reading" lists, Reading Goals, and re-read tracking. Per
    the design doc, a Work is "completed" if any of its Editions is
    completed; this row reflects that aggregated answer.
    """

    __tablename__ = "reading_states"
    __table_args__ = (
        UniqueConstraint("user_id", "work_id", name="uq_reading_state_user_work"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    work_id: Mapped[int] = mapped_column(ForeignKey("works.id"), index=True)

    # Lifecycle
    status: Mapped[str] = mapped_column(
        String(20), default=STATUS_WANT_TO_READ, nullable=False
    )
    # Whispersync TimesStartedReading — bumped on each
    # `completed → reading` (or `want_to_read → reading`) transition.
    times_started: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # For re-read tracking — bumped on each `reading → completed`.
    times_completed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_opened: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Personal valuation
    rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 1-5
    review: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Sum of reading time across all devices and formats for this Work.
    total_time_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )


class EditionPosition(Base):
    """Per-edition canonical cursor + furthest-read watermark.

    The cursor is a tagged union: ``current_format`` says how to
    interpret ``current_value`` (a CFI string, ``"chapter_href#span_id"``,
    a millisecond audio offset, etc.). ``current_pct`` is the universal
    0–1 fallback every client can render.

    ``furthest_*`` is monotonically non-decreasing. The only way to
    regress it is via an explicit reset (``furthest_reset_at`` is the
    audit trail). Per the design doc, no auto-reset on re-read.
    """

    __tablename__ = "edition_positions"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "edition_id", name="uq_edition_position_user_edition"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    edition_id: Mapped[int] = mapped_column(ForeignKey("editions.id"), index=True)

    # Current cursor — last-write-wins on (timestamp, device).
    current_format: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    current_value: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    current_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    current_device_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("devices.id"), nullable=True
    )
    current_updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )

    # Furthest-read watermark.
    furthest_format: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    furthest_value: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    furthest_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    furthest_updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    furthest_reset_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )

    # Per-edition stats — page counts and time-spent are format-specific
    # so they can't live on the work-keyed ReadingState.
    total_pages: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    time_spent_seconds: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    # Device-reported "minutes left in this book" estimate. Populated
    # by Kobo (Statistics.RemainingTimeMinutes) and any other reader
    # that ships its own pace tracking; the web reader's user-pace
    # fallback (future) reads this when present and computes its own
    # otherwise. Optional because not every device reports it.
    remaining_time_minutes: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )


class DevicePosition(Base):
    """Per-(user, edition, device) last-known native position.

    Optional but useful: enables "last read on Lisa's Kobo Libra 3
    hours ago, 47%" UX, lets each device restore its own cursor cleanly
    even when another device has written a more recent
    ``EditionPosition``, and serves as a debugging breadcrumb.

    ``raw_payload`` keeps the device's full last-sync JSON for
    diagnostics; the live cursor is in ``format`` / ``value`` / ``pct``.
    """

    __tablename__ = "device_positions"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "edition_id",
            "device_id",
            name="uq_device_position_user_edition_device",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    edition_id: Mapped[int] = mapped_column(ForeignKey("editions.id"), index=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), index=True)

    format: Mapped[str] = mapped_column(String(32), nullable=False)
    value: Mapped[str] = mapped_column(String(2048), nullable=False)
    pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    raw_payload: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )
