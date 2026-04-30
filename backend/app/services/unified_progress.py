"""Unified progress write path.

Single helper that any client (web reader, Kobo sync, future audiobook
player, future native mobile) calls when reporting a reading-position
update. Writes the three new tables consistently:

- ``EditionPosition`` — current cursor (last-write-wins on timestamp)
  and the monotonic furthest-read watermark.
- ``DevicePosition`` — per-device snapshot, when ``device_id`` is given.
- ``ReadingState`` — work-level lifecycle (status, re-read counters,
  reading time, timestamps).

Status transitions follow the design (``personal/design/
unified_progress_schema.md`` §5):

- ``want_to_read → reading`` when first cursor write with ``pct > 0``;
  ``times_started`` bumped, ``started_at`` set.
- ``reading → completed`` when ``pct >= 0.97`` or an explicit
  ``status_hint='completed'`` (Kobo's ``Finished``); ``times_completed``
  bumped, ``completed_at`` set.
- ``completed → reading`` (re-read) when the user reopens the book at
  low position (``pct < 0.10``) without a ``status_hint``;
  ``times_started`` bumped. The furthest-read watermark is **not**
  reset — that's manual only.

Step 3a (this commit) calls this helper *in addition to* the legacy
ReadProgress / KoboBookState / UserEdition writes. Read paths still
serve from the legacy tables until step 3b switches them.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.edition import Edition
from app.models.reading import (
    STATUS_ABANDONED,
    STATUS_COMPLETED,
    STATUS_READING,
    STATUS_WANT_TO_READ,
    DevicePosition,
    EditionPosition,
    ReadingState,
)

COMPLETION_THRESHOLD = 0.97          # pct ≥ this on write → auto-complete
REREAD_REOPEN_THRESHOLD = 0.10       # completed + open at this pct → re-read


async def write_progress(
    db: AsyncSession,
    *,
    user_id: int,
    edition: Edition,
    cursor_format: Optional[str],
    cursor_value: Optional[str],
    cursor_pct: float,
    device_id: Optional[int] = None,
    raw_payload: Optional[str] = None,
    total_pages: Optional[int] = None,
    time_spent_delta_seconds: int = 0,
    status_hint: Optional[str] = None,
    rating: Optional[int] = None,
    review: Optional[str] = None,
    timestamp: Optional[datetime] = None,
    # Kobo-flavoured extras: optional, populated when the upstream
    # device reports them. The web reader doesn't compute these; they
    # let later features (time-left UI, multi-device reconciliation)
    # consume Kobo's own estimate without re-deriving.
    remaining_time_minutes: Optional[int] = None,
) -> None:
    """Apply one progress update to the unified schema.

    Idempotent in the sense that callers can write the same payload
    repeatedly without corrupting state — the cursor is overwritten if
    newer, the watermark only advances, the time delta sums.

    All writes happen in the caller's transaction; the caller commits.
    """
    if cursor_pct is None:
        cursor_pct = 0.0
    cursor_pct = max(0.0, min(1.0, float(cursor_pct)))
    timestamp = timestamp or datetime.utcnow()

    # ── DevicePosition (per-(user, edition, device) snapshot) ─────────
    if device_id is not None and cursor_format and cursor_value is not None:
        dp = (
            await db.execute(
                select(DevicePosition).where(
                    DevicePosition.user_id == user_id,
                    DevicePosition.edition_id == edition.id,
                    DevicePosition.device_id == device_id,
                )
            )
        ).scalar_one_or_none()
        if dp is None:
            dp = DevicePosition(
                user_id=user_id,
                edition_id=edition.id,
                device_id=device_id,
                format=cursor_format,
                value=cursor_value,
                pct=cursor_pct,
                raw_payload=raw_payload,
            )
            db.add(dp)
        else:
            dp.format = cursor_format
            dp.value = cursor_value
            dp.pct = cursor_pct
            if raw_payload is not None:
                dp.raw_payload = raw_payload
            dp.updated_at = timestamp

    # ── EditionPosition (canonical cursor + furthest watermark) ───────
    ep = (
        await db.execute(
            select(EditionPosition).where(
                EditionPosition.user_id == user_id,
                EditionPosition.edition_id == edition.id,
            )
        )
    ).scalar_one_or_none()
    if ep is None:
        ep = EditionPosition(
            user_id=user_id,
            edition_id=edition.id,
            current_format=cursor_format,
            current_value=cursor_value,
            current_pct=cursor_pct,
            current_device_id=device_id,
            current_updated_at=timestamp,
            furthest_format=cursor_format,
            furthest_value=cursor_value,
            furthest_pct=cursor_pct,
            furthest_updated_at=timestamp,
            total_pages=total_pages,
            time_spent_seconds=max(0, time_spent_delta_seconds),
            remaining_time_minutes=remaining_time_minutes,
        )
        db.add(ep)
    else:
        # Cursor: overwrite if incoming is newer than what's stored.
        if (
            ep.current_updated_at is None
            or timestamp >= ep.current_updated_at
        ):
            ep.current_format = cursor_format or ep.current_format
            ep.current_value = cursor_value if cursor_value is not None else ep.current_value
            ep.current_pct = cursor_pct
            ep.current_device_id = device_id
            ep.current_updated_at = timestamp
        # Furthest: monotonic non-decreasing.
        if cursor_pct > (ep.furthest_pct or 0.0):
            ep.furthest_format = cursor_format or ep.furthest_format
            ep.furthest_value = cursor_value if cursor_value is not None else ep.furthest_value
            ep.furthest_pct = cursor_pct
            ep.furthest_updated_at = timestamp
        # total_pages: take the max of any non-null observation.
        if total_pages and (ep.total_pages is None or total_pages > ep.total_pages):
            ep.total_pages = total_pages
        # Time-spent accumulates.
        if time_spent_delta_seconds > 0:
            ep.time_spent_seconds = (ep.time_spent_seconds or 0) + time_spent_delta_seconds
        # Remaining-time estimate: only overwrite when the caller
        # actually supplied one. None means "no signal this update,"
        # which shouldn't clobber a prior estimate.
        if remaining_time_minutes is not None:
            ep.remaining_time_minutes = remaining_time_minutes

    # ── ReadingState (work-level lifecycle) ───────────────────────────
    work_id = edition.work_id
    if work_id is None:
        return  # orphaned edition; nothing to aggregate at the work level

    rs = (
        await db.execute(
            select(ReadingState).where(
                ReadingState.user_id == user_id,
                ReadingState.work_id == work_id,
            )
        )
    ).scalar_one_or_none()
    if rs is None:
        rs = ReadingState(
            user_id=user_id,
            work_id=work_id,
            status=STATUS_WANT_TO_READ,
            times_started=0,
            times_completed=0,
            total_time_seconds=0,
        )
        db.add(rs)

    prior_status = rs.status
    new_status = _resolve_status_transition(
        current=prior_status,
        cursor_pct=cursor_pct,
        status_hint=status_hint,
    )
    rs.status = new_status

    if new_status != prior_status:
        if new_status == STATUS_READING:
            rs.times_started = (rs.times_started or 0) + 1
            if rs.started_at is None:
                rs.started_at = timestamp
        elif new_status == STATUS_COMPLETED:
            rs.times_completed = (rs.times_completed or 0) + 1
            rs.completed_at = timestamp

    if rs.last_opened is None or timestamp > rs.last_opened:
        rs.last_opened = timestamp
    if rating is not None:
        rs.rating = rating
    if review is not None:
        rs.review = review
    if time_spent_delta_seconds > 0:
        rs.total_time_seconds = (rs.total_time_seconds or 0) + time_spent_delta_seconds


def _resolve_status_transition(
    *,
    current: str,
    cursor_pct: float,
    status_hint: Optional[str],
) -> str:
    """Decide the new lifecycle status from a position update.

    Pure function — no DB access, easy to test.
    """
    # Explicit hints from devices win (Kobo's "Finished" / "Reading").
    if status_hint == STATUS_COMPLETED:
        return STATUS_COMPLETED
    if status_hint == STATUS_READING:
        return STATUS_READING
    if status_hint == STATUS_ABANDONED:
        return STATUS_ABANDONED

    # Auto-completion when the cursor crosses the threshold.
    if cursor_pct >= COMPLETION_THRESHOLD:
        return STATUS_COMPLETED

    # Re-read detection: completed → reading when reopened at the start.
    if current == STATUS_COMPLETED and cursor_pct <= REREAD_REOPEN_THRESHOLD:
        return STATUS_READING

    # Want-to-read → reading on first non-zero cursor.
    if current == STATUS_WANT_TO_READ and cursor_pct > 0:
        return STATUS_READING

    return current
