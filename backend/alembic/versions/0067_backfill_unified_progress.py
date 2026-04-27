"""backfill unified progress schema from ReadProgress + KoboBookState + UserEdition

Step 2 of the four-step migration to a unified progress schema. Reads
the three legacy tables and populates ``reading_states``,
``edition_positions``, and ``device_positions``.

Idempotent: uses INSERT OR IGNORE on the unique constraints. First run
fills everything; re-runs are no-ops because the unique keys already
exist. This protects against accidental re-execution after the read
switch (0068+) lands and the new tables receive live writes — the
backfill cannot clobber a row that's already there.

DevicePosition is intentionally NOT backfilled. Per the design doc
(§4) those rows only have value when fresh; backfilling synthetic
device positions from legacy state would be misleading.

Pre-condition: all status values in the legacy tables must already be
canonical strings (``want_to_read`` / ``reading`` / ``completed`` /
``abandoned``). The household DB was inventoried before this migration
was written and contains only those values; if your DB was hand-edited
to contain raw Kobo enum strings (``ReadyToRead`` / ``Reading`` /
``Finished``), translate them first with the verification script's
``--map-kobo-statuses`` flag.

Verification: run ``personal/scripts/verify_progress_migration.py``
after upgrade to compare every (user, edition) in the legacy tables
against the new tables and hard-fail on mismatches.

Design: ``personal/design/unified_progress_schema.md``.

Revision ID: 0067
Revises: 0066
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0067"
down_revision = "0066"


# Map Kobo enum statuses to canonical lifecycle statuses. The household
# DB doesn't contain Kobo strings as of this migration, but kobo_sync
# code paths could create them; the mapping is used defensively.
_KOBO_STATUS_MAP = {
    "ReadyToRead": "want_to_read",
    "Reading": "reading",
    "Finished": "completed",
}


def _canonical_status(raw: str | None) -> str | None:
    """Translate any known status form into the canonical lifecycle string."""
    if raw is None:
        return None
    return _KOBO_STATUS_MAP.get(raw, raw)


def upgrade() -> None:
    bind = op.get_bind()

    # ── EditionPosition: one row per (user, edition) found in any
    # legacy source. We pick the most-recently-updated source as the
    # current cursor; furthest_pct is the max percentage seen across
    # all sources for this (user, edition). ────────────────────────────

    # Union of (user_id, edition_id) seen anywhere.
    pairs = bind.execute(
        sa.text(
            """
            SELECT DISTINCT user_id, edition_id FROM read_progress
            UNION
            SELECT DISTINCT user_id, edition_id FROM kobo_book_states
            UNION
            SELECT DISTINCT user_id, edition_id FROM user_editions
            """
        )
    ).fetchall()

    for user_id, edition_id in pairs:
        rp = bind.execute(
            sa.text(
                "SELECT current_page, total_pages, percentage, status, "
                "rating, cfi, started_at, completed_at, last_opened, updated_at "
                "FROM read_progress WHERE user_id = :u AND edition_id = :e"
            ),
            {"u": user_id, "e": edition_id},
        ).first()
        kbs = bind.execute(
            sa.text(
                "SELECT status, times_started_reading, total_pages, current_page, "
                "time_spent_reading, content_source_progress, spine_index, "
                "content_id, updated_at "
                "FROM kobo_book_states WHERE user_id = :u AND edition_id = :e"
            ),
            {"u": user_id, "e": edition_id},
        ).first()
        ue = bind.execute(
            sa.text(
                "SELECT status, current_page, total_pages, percentage, rating, "
                "review, started_at, completed_at, last_opened, updated_at "
                "FROM user_editions WHERE user_id = :u AND edition_id = :e"
            ),
            {"u": user_id, "e": edition_id},
        ).first()

        # Pick the freshest cursor source by updated_at.
        candidates = []
        if rp:
            cfi = rp.cfi
            if cfi:
                candidates.append(
                    ("cfi", cfi, (rp.percentage or 0) / 100.0, rp.updated_at)
                )
            else:
                candidates.append(
                    (
                        "percent",
                        str(rp.percentage or 0),
                        (rp.percentage or 0) / 100.0,
                        rp.updated_at,
                    )
                )
        if kbs:
            content_id = kbs.content_id or ""
            spine_index = kbs.spine_index or 0
            kobo_value = f"{content_id}#spine#{spine_index}"
            candidates.append(
                (
                    "kobo_span",
                    kobo_value,
                    (kbs.content_source_progress or 0) / 100.0,
                    kbs.updated_at,
                )
            )
        if ue and not (rp or kbs):
            # UserEdition is the only source — synthesize a percent cursor.
            candidates.append(
                (
                    "percent",
                    str(ue.percentage or 0),
                    (ue.percentage or 0) / 100.0,
                    ue.updated_at,
                )
            )

        if not candidates:
            continue

        # Sort by updated_at (None last). The one with the freshest
        # timestamp owns the current cursor.
        candidates.sort(
            key=lambda c: (c[3] is None, c[3] or ""), reverse=False
        )
        current_format, current_value, current_pct, current_updated_at = candidates[-1]

        # Furthest = max pct across all candidates and the UserEdition
        # percentage if it exists.
        all_pcts = [c[2] for c in candidates]
        if ue:
            all_pcts.append((ue.percentage or 0) / 100.0)
        furthest_pct = max(all_pcts)
        # Pick the candidate that hit the furthest_pct as the
        # furthest_format/value triple.
        furthest_candidate = max(candidates, key=lambda c: c[2])
        furthest_format = furthest_candidate[0]
        furthest_value = furthest_candidate[1]
        furthest_updated_at = furthest_candidate[3]

        total_pages_candidates = [
            x for x in [
                rp.total_pages if rp else None,
                kbs.total_pages if kbs else None,
                ue.total_pages if ue else None,
            ] if x
        ]
        total_pages = max(total_pages_candidates) if total_pages_candidates else None
        time_spent_seconds = (kbs.time_spent_reading if kbs else 0) or 0

        bind.execute(
            sa.text(
                """
                INSERT OR IGNORE INTO edition_positions (
                    user_id, edition_id,
                    current_format, current_value, current_pct,
                    current_updated_at,
                    furthest_format, furthest_value, furthest_pct,
                    furthest_updated_at,
                    total_pages, time_spent_seconds,
                    created_at, updated_at
                ) VALUES (
                    :user_id, :edition_id,
                    :current_format, :current_value, :current_pct,
                    :current_updated_at,
                    :furthest_format, :furthest_value, :furthest_pct,
                    :furthest_updated_at,
                    :total_pages, :time_spent_seconds,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                """
            ),
            {
                "user_id": user_id,
                "edition_id": edition_id,
                "current_format": current_format,
                "current_value": current_value,
                "current_pct": current_pct,
                "current_updated_at": current_updated_at,
                "furthest_format": furthest_format,
                "furthest_value": furthest_value,
                "furthest_pct": furthest_pct,
                "furthest_updated_at": furthest_updated_at,
                "total_pages": total_pages,
                "time_spent_seconds": time_spent_seconds,
            },
        )

    # ── ReadingState: one row per (user, work) aggregating across the
    # work's editions. status follows the design rule (completed if any,
    # then reading if any, then abandoned if any, else want_to_read).
    # ──────────────────────────────────────────────────────────────────

    # Build the (user_id, work_id) set from each source via the editions
    # table.
    work_pairs = bind.execute(
        sa.text(
            """
            SELECT DISTINCT t.user_id, e.work_id
            FROM (
                SELECT user_id, edition_id FROM read_progress
                UNION
                SELECT user_id, edition_id FROM kobo_book_states
                UNION
                SELECT user_id, edition_id FROM user_editions
            ) t
            JOIN editions e ON e.id = t.edition_id
            WHERE e.work_id IS NOT NULL
            """
        )
    ).fetchall()

    for user_id, work_id in work_pairs:
        # Pull all per-edition state rows for this (user, work).
        rows = bind.execute(
            sa.text(
                """
                SELECT
                    rp.status   AS rp_status,
                    rp.rating   AS rp_rating,
                    rp.started_at AS rp_started_at,
                    rp.completed_at AS rp_completed_at,
                    rp.last_opened AS rp_last_opened,
                    kbs.status  AS kbs_status,
                    kbs.times_started_reading AS kbs_times_started,
                    kbs.time_spent_reading AS kbs_time_spent,
                    kbs.updated_at AS kbs_updated_at,
                    ue.status   AS ue_status,
                    ue.rating   AS ue_rating,
                    ue.review   AS ue_review,
                    ue.started_at AS ue_started_at,
                    ue.completed_at AS ue_completed_at,
                    ue.last_opened AS ue_last_opened
                FROM editions e
                LEFT JOIN read_progress rp
                    ON rp.user_id = :u AND rp.edition_id = e.id
                LEFT JOIN kobo_book_states kbs
                    ON kbs.user_id = :u AND kbs.edition_id = e.id
                LEFT JOIN user_editions ue
                    ON ue.user_id = :u AND ue.edition_id = e.id
                WHERE e.work_id = :w
                  AND (rp.id IS NOT NULL OR kbs.id IS NOT NULL OR ue.id IS NOT NULL)
                """
            ),
            {"u": user_id, "w": work_id},
        ).fetchall()

        if not rows:
            continue

        statuses: list[str] = []
        ratings: list[int] = []
        review: str | None = None
        starteds: list = []
        completeds: list = []
        last_openeds: list = []
        times_started_max = 0
        total_time = 0

        for r in rows:
            for raw in (r.rp_status, _canonical_status(r.kbs_status), r.ue_status):
                if raw:
                    statuses.append(raw)
            for raw in (r.rp_rating, r.ue_rating):
                if raw is not None:
                    ratings.append(raw)
            if r.ue_review and not review:
                review = r.ue_review
            for raw in (r.rp_started_at, r.ue_started_at):
                if raw:
                    starteds.append(raw)
            for raw in (r.rp_completed_at, r.ue_completed_at):
                if raw:
                    completeds.append(raw)
            for raw in (r.rp_last_opened, r.ue_last_opened, r.kbs_updated_at):
                if raw:
                    last_openeds.append(raw)
            if r.kbs_times_started:
                times_started_max = max(times_started_max, r.kbs_times_started)
            if r.kbs_time_spent:
                total_time += r.kbs_time_spent

        # Resolve work-level status per the design (completed-if-any).
        if "completed" in statuses:
            status = "completed"
        elif "reading" in statuses:
            status = "reading"
        elif "abandoned" in statuses:
            status = "abandoned"
        else:
            status = "want_to_read"

        # times_started: prefer the Kobo counter; otherwise infer 1 if
        # the user has gotten past 'want_to_read'.
        times_started = times_started_max
        if times_started == 0 and status != "want_to_read":
            times_started = 1
        # times_completed: best-effort 1 if completed, 0 otherwise. Real
        # re-read tracking begins after this migration.
        times_completed = 1 if status == "completed" else 0

        rating = ratings[0] if ratings else None
        started_at = min(starteds) if starteds else None
        completed_at = max(completeds) if (completeds and status == "completed") else None
        last_opened = max(last_openeds) if last_openeds else None

        bind.execute(
            sa.text(
                """
                INSERT OR IGNORE INTO reading_states (
                    user_id, work_id, status,
                    times_started, times_completed,
                    started_at, completed_at, last_opened,
                    rating, review,
                    total_time_seconds,
                    created_at, updated_at
                ) VALUES (
                    :user_id, :work_id, :status,
                    :times_started, :times_completed,
                    :started_at, :completed_at, :last_opened,
                    :rating, :review,
                    :total_time_seconds,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                """
            ),
            {
                "user_id": user_id,
                "work_id": work_id,
                "status": status,
                "times_started": times_started,
                "times_completed": times_completed,
                "started_at": started_at,
                "completed_at": completed_at,
                "last_opened": last_opened,
                "rating": rating,
                "review": review,
                "total_time_seconds": total_time,
            },
        )


def downgrade() -> None:
    # Reversing a backfill is a destructive op (legacy tables still hold
    # the source of truth at this stage). We could TRUNCATE the new
    # tables, but the safe move is to require an explicit operator
    # action. Keeping downgrade as a no-op preserves whatever state has
    # been written into the new tables since 0067 ran.
    pass
