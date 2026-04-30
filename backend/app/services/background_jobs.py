"""CRUD helpers for DB-backed background job tracking."""

import json
import uuid
from datetime import datetime

from app.database import get_session_factory
from app.models.background_job import BackgroundJob


def _to_dict(job: BackgroundJob) -> dict:
    """Flatten a BackgroundJob row into the dict format the API returns."""
    d = {
        "status": job.status,
        "total": job.total,
        "done": job.done,
        "failed": job.failed,
        "current": job.current or "",
        "started_at": job.started_at,
    }
    if job.counters:
        d.update(json.loads(job.counters))
    return d


async def create_job(
    job_type: str,
    total: int,
    extra_counters: dict | None = None,
) -> tuple[str, dict]:
    """Insert a new job row. Returns (job_id, flat_dict)."""
    job_id = str(uuid.uuid4())
    started_at = datetime.utcnow().isoformat()
    counters_json = json.dumps(extra_counters) if extra_counters else None

    job = BackgroundJob(
        id=job_id,
        job_type=job_type,
        status="queued",
        total=total,
        done=0,
        failed=0,
        current="",
        started_at=started_at,
        counters=counters_json,
    )

    factory = get_session_factory()
    async with factory() as db:
        db.add(job)
        await db.commit()

    return job_id, _to_dict(job)


async def get_job(job_id: str) -> dict | None:
    """Load a job by ID. Returns flat dict or None."""
    factory = get_session_factory()
    async with factory() as db:
        job = await db.get(BackgroundJob, job_id)
        if not job:
            return None
        return _to_dict(job)


async def get_active_job(job_type: str) -> tuple[str, dict] | None:
    """Find a running/queued job of a given type. Returns (job_id, dict) or None."""
    from sqlalchemy import select

    factory = get_session_factory()
    async with factory() as db:
        stmt = (
            select(BackgroundJob)
            .where(BackgroundJob.job_type == job_type)
            .where(BackgroundJob.status.in_(["running", "queued"]))
            .order_by(BackgroundJob.started_at.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        job = result.scalar_one_or_none()
        if not job:
            return None
        return job.id, _to_dict(job)


async def update_job(job_id: str, **fields) -> None:
    """Update common fields and/or counters on a job.

    Common fields (status, done, failed, current, total) are set directly.
    Anything else is merged into the JSON counters column.
    """
    COMMON = {"status", "done", "failed", "current", "total", "started_at"}

    factory = get_session_factory()
    async with factory() as db:
        job = await db.get(BackgroundJob, job_id)
        if not job:
            return

        extra = {}
        for k, v in fields.items():
            if k in COMMON:
                setattr(job, k, v)
            else:
                extra[k] = v

        if extra:
            existing = json.loads(job.counters) if job.counters else {}
            existing.update(extra)
            job.counters = json.dumps(existing)

        await db.commit()


async def get_job_status(job_id: str) -> str | None:
    """Quick check of just the status field (for cancel-polling in loops)."""
    factory = get_session_factory()
    async with factory() as db:
        job = await db.get(BackgroundJob, job_id)
        return job.status if job else None


# ── Sync versions for background threads ─────────────────────────

import sqlite3

from app.config import get_settings


def _get_sync_db_path() -> str:
    """Get the SQLite database path for sync access."""
    url = get_settings().DATABASE_URL
    # sqlite+aiosqlite:////data/config/scriptorium.db → /data/config/scriptorium.db
    path = url.split("///")[-1]
    return path


def sync_update_job(job_id: str, **fields) -> None:
    """Sync version of update_job for use in background threads."""
    COMMON = {"status", "done", "failed", "current", "total"}
    db_path = _get_sync_db_path()

    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT counters FROM background_jobs WHERE id = ?", (job_id,)
        ).fetchone()
        if not row:
            return

        sets = []
        params = []
        extra = {}
        for k, v in fields.items():
            if k in COMMON:
                sets.append(f"{k} = ?")
                params.append(v)
            else:
                extra[k] = v

        if extra:
            existing = json.loads(row[0]) if row[0] else {}
            existing.update(extra)
            sets.append("counters = ?")
            params.append(json.dumps(existing))

        if sets:
            params.append(job_id)
            conn.execute(
                f"UPDATE background_jobs SET {', '.join(sets)} WHERE id = ?",
                params,
            )
            conn.commit()
    finally:
        conn.close()


def sync_get_job_status(job_id: str) -> str | None:
    """Sync version of get_job_status for use in background threads."""
    db_path = _get_sync_db_path()
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT status FROM background_jobs WHERE id = ?", (job_id,)
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()
