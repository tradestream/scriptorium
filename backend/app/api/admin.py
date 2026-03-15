"""Admin-only endpoints: config read, backup/restore, bulk enrichment."""

import asyncio
import io
import logging
import tarfile
import uuid as _uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db, _session_factory
from app.models.user import User

from .auth import get_current_user

logger = logging.getLogger(__name__)

# ── In-memory bulk-enrich job store ───────────────────────────────────────────
# { job_id: { status, total, done, failed, current, started_at, error } }
_bulk_jobs: dict[str, dict] = {}

router = APIRouter(prefix="/admin")


class NamingSettingsUpdate(BaseModel):
    naming_enabled: bool
    naming_pattern: str


class EnrichmentKeysUpdate(BaseModel):
    hardcover_api_key: str | None = None
    comicvine_api_key: str | None = None
    google_books_api_key: str | None = None
    isbndb_api_key: str | None = None
    amazon_cookie: str | None = None
    librarything_api_key: str | None = None


def _require_admin(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return current_user


async def _get_system_settings(db: AsyncSession):
    """Load the single-row SystemSettings record (or None if not yet created)."""
    from sqlalchemy import select
    from app.models.system import SystemSettings
    result = await db.execute(select(SystemSettings).where(SystemSettings.id == 1))
    return result.scalar_one_or_none()


@router.get("/config")
async def get_config(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(_require_admin),
):
    """Return non-secret config values for the settings UI."""
    settings = get_settings()
    data = {
        "smtp_configured": bool(settings.SMTP_HOST),
        "smtp_host": settings.SMTP_HOST,
        "smtp_port": settings.SMTP_PORT,
        "smtp_user": settings.SMTP_USER,
        "smtp_from": settings.SMTP_FROM,
        "smtp_tls": settings.SMTP_TLS,
        "ingest_auto_convert": settings.INGEST_AUTO_CONVERT,
        "ingest_target_format": settings.INGEST_TARGET_FORMAT,
        "ingest_auto_enrich": settings.INGEST_AUTO_ENRICH,
        "ingest_default_provider": settings.INGEST_DEFAULT_PROVIDER,
        "oidc_enabled": settings.OIDC_ENABLED,
        "oidc_configured": bool(settings.OIDC_ENABLED and settings.OIDC_CLIENT_ID),
        "oidc_discovery_url": settings.OIDC_DISCOVERY_URL,
        "llm_provider": settings.LLM_PROVIDER,
        "llm_configured": bool(
            settings.ANTHROPIC_API_KEY or settings.OPENAI_API_KEY
            or settings.LLM_PROVIDER == "ollama"
        ),
        "calibre_path": settings.CALIBRE_PATH,
        "library_path": settings.LIBRARY_PATH,
        "ingest_path": settings.INGEST_PATH,
        "loose_leaves_path": settings.LOOSE_LEAVES_PATH,
        # Enrichment provider key status — checked via _get_key() which honors DB overrides
        "hardcover_configured": False,  # updated below after loading sys_settings
        "comicvine_configured": False,
        "google_books_configured": False,
        "isbndb_configured": False,
        "amazon_configured": False,
        "librarything_configured": False,
        # File naming — env defaults, may be overridden by DB below
        "naming_enabled": settings.LIBRARY_NAMING_ENABLED,
        "naming_pattern": settings.LIBRARY_NAMING_PATTERN or "{authors}/{title}",
        # AudiobookShelf
        "abs_configured": bool(settings.ABS_URL and settings.ABS_API_KEY),
        "abs_url": settings.ABS_URL,
    }
    # Override naming + enrichment key status from DB if a row exists
    from app.services.metadata_enrichment import _get_key
    sys_settings = await _get_system_settings(db)
    if sys_settings is not None:
        data["naming_enabled"] = sys_settings.naming_enabled
        data["naming_pattern"] = sys_settings.naming_pattern or data["naming_pattern"]
    data["hardcover_configured"] = bool(_get_key("HARDCOVER_API_KEY"))
    data["comicvine_configured"] = bool(_get_key("COMICVINE_API_KEY"))
    data["google_books_configured"] = bool(_get_key("GOOGLE_BOOKS_API_KEY"))
    data["isbndb_configured"] = bool(_get_key("ISBNDB_API_KEY"))
    data["amazon_configured"] = bool(_get_key("AMAZON_COOKIE"))
    data["librarything_configured"] = bool(_get_key("LIBRARYTHING_API_KEY"))
    return data


@router.get("/naming")
async def get_naming_settings(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(_require_admin),
):
    """Return current naming settings (DB if set, else env fallback)."""
    settings = get_settings()
    sys_settings = await _get_system_settings(db)
    if sys_settings is not None:
        return {
            "naming_enabled": sys_settings.naming_enabled,
            "naming_pattern": sys_settings.naming_pattern or settings.LIBRARY_NAMING_PATTERN or "{authors}/{title}",
        }
    return {
        "naming_enabled": settings.LIBRARY_NAMING_ENABLED,
        "naming_pattern": settings.LIBRARY_NAMING_PATTERN or "{authors}/{title}",
    }


@router.put("/naming")
async def update_naming_settings(
    body: NamingSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(_require_admin),
):
    """Save global naming settings to the database."""
    from sqlalchemy import select
    from app.models.system import SystemSettings
    result = await db.execute(select(SystemSettings).where(SystemSettings.id == 1))
    row = result.scalar_one_or_none()
    if row is None:
        row = SystemSettings(id=1, naming_enabled=body.naming_enabled, naming_pattern=body.naming_pattern)
        db.add(row)
    else:
        row.naming_enabled = body.naming_enabled
        row.naming_pattern = body.naming_pattern
    await db.commit()
    return {"naming_enabled": row.naming_enabled, "naming_pattern": row.naming_pattern}


@router.put("/enrichment")
async def update_enrichment_keys(
    body: EnrichmentKeysUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(_require_admin),
):
    """Save enrichment API keys to the database. Empty string = clear the key."""
    from sqlalchemy import select
    from app.models.system import SystemSettings
    from app.services.metadata_enrichment import apply_enrichment_key_overrides

    result = await db.execute(select(SystemSettings).where(SystemSettings.id == 1))
    row = result.scalar_one_or_none()
    if row is None:
        row = SystemSettings(id=1)
        db.add(row)

    # Empty string means "clear this key"; None means "don't change"
    def _apply(field: str, value: str | None, current):
        if value is None:
            return current  # not sent — keep existing
        return value.strip() or None  # empty string → clear

    row.hardcover_api_key = _apply("hardcover_api_key", body.hardcover_api_key, row.hardcover_api_key)
    row.comicvine_api_key = _apply("comicvine_api_key", body.comicvine_api_key, row.comicvine_api_key)
    row.google_books_api_key = _apply("google_books_api_key", body.google_books_api_key, row.google_books_api_key)
    row.isbndb_api_key = _apply("isbndb_api_key", body.isbndb_api_key, row.isbndb_api_key)
    row.amazon_cookie = _apply("amazon_cookie", body.amazon_cookie, row.amazon_cookie)
    row.librarything_api_key = _apply("librarything_api_key", body.librarything_api_key, row.librarything_api_key)

    await db.commit()

    # Update in-memory overrides immediately — no restart needed
    apply_enrichment_key_overrides({
        "HARDCOVER_API_KEY": row.hardcover_api_key,
        "COMICVINE_API_KEY": row.comicvine_api_key,
        "GOOGLE_BOOKS_API_KEY": row.google_books_api_key,
        "ISBNDB_API_KEY": row.isbndb_api_key,
        "AMAZON_COOKIE": row.amazon_cookie,
        "LIBRARYTHING_API_KEY": row.librarything_api_key,
    })

    return {
        "hardcover_configured": bool(row.hardcover_api_key),
        "comicvine_configured": bool(row.comicvine_api_key),
        "google_books_configured": bool(row.google_books_api_key),
        "isbndb_configured": bool(row.isbndb_api_key),
        "amazon_configured": bool(row.amazon_cookie),
        "librarything_configured": bool(row.librarything_api_key),
    }


@router.get("/naming/preview")
async def preview_naming_pattern(
    pattern: str = "{authors}/{title}",
    _admin: User = Depends(_require_admin),
):
    """Return an example resolved path for a given naming pattern."""
    from app.services.naming import preview as _preview
    try:
        return {"pattern": pattern, "example": _preview(pattern)}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


class BulkEnrichOptions(BaseModel):
    library_id: Optional[int] = None
    missing_cover: bool = False
    missing_description: bool = False
    missing_authors: bool = False
    force: bool = False
    provider: Optional[str] = None


@router.post("/enrich/bulk")
async def start_bulk_enrich(
    opts: BulkEnrichOptions,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(_require_admin),
):
    """Start a background bulk-enrichment job.

    Filters: library_id, missing_cover, missing_description, missing_authors.
    Returns a job_id for polling via GET /admin/enrich/bulk/{job_id}.
    """
    from sqlalchemy import select
    from app.models.edition import Edition
    from app.models.work import Work
    from sqlalchemy.orm import joinedload

    # Build filtered edition list up front
    stmt = (
        select(Edition)
        .join(Edition.work)
        .options(
            joinedload(Edition.work).options(joinedload(Work.authors), joinedload(Work.tags)),
            joinedload(Edition.files),
        )
    )
    if opts.library_id:
        stmt = stmt.where(Edition.library_id == opts.library_id)
    if opts.missing_cover:
        stmt = stmt.where(Edition.cover_hash.is_(None))
    if opts.missing_description:
        stmt = stmt.where(Work.description.is_(None))
    if opts.missing_authors:
        stmt = stmt.where(~Work.authors.any())

    result = await db.execute(stmt)
    editions = result.unique().scalars().all()

    job_id = str(_uuid.uuid4())
    _bulk_jobs[job_id] = {
        "status": "queued",
        "total": len(editions),
        "done": 0,
        "failed": 0,
        "current": "",
        "started_at": datetime.utcnow().isoformat(),
        "error": None,
    }

    # Collect IDs only — the background task opens its own session
    edition_ids = [e.id for e in editions]
    background_tasks.add_task(_run_bulk_enrich, job_id, edition_ids, opts.force, opts.provider)

    return {"job_id": job_id, "total": len(editions)}


@router.get("/enrich/bulk/{job_id}")
async def get_bulk_enrich_job(
    job_id: str,
    _admin: User = Depends(_require_admin),
):
    """Poll the status of a bulk-enrichment job."""
    job = _bulk_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": job_id, **job}


@router.delete("/enrich/bulk/{job_id}", status_code=204)
async def cancel_bulk_enrich_job(
    job_id: str,
    _admin: User = Depends(_require_admin),
):
    """Mark a bulk-enrichment job as cancelled (best-effort)."""
    job = _bulk_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] == "running":
        job["status"] = "cancelled"


async def _run_bulk_enrich(
    job_id: str,
    edition_ids: list[int],
    force: bool,
    provider: Optional[str],
) -> None:
    """Background task: enrich each edition, update job state."""
    from app.api.books import _apply_enrichment, _edition_options
    from app.database import _session_factory
    from app.models.edition import Edition
    from app.models.work import Work
    from app.services.metadata_enrichment import enrichment_service
    from app.services.search import search_service
    from app.services.events import broadcaster
    from sqlalchemy import select
    from sqlalchemy.orm import joinedload

    job = _bulk_jobs[job_id]
    job["status"] = "running"
    total = len(edition_ids)

    async with _session_factory() as db:
        for i, edition_id in enumerate(edition_ids):
            if job.get("status") == "cancelled":
                break

            # Reload edition fresh each iteration
            stmt = (
                select(Edition)
                .where(Edition.id == edition_id)
                .options(*_edition_options())
            )
            result = await db.execute(stmt)
            edition = result.unique().scalar_one_or_none()
            if not edition:
                job["failed"] += 1
                continue

            work = edition.work
            job["current"] = work.title

            try:
                author_names = [a.name for a in work.authors]
                file_ext = f".{edition.files[0].format}" if edition.files else None

                if provider:
                    enriched = await enrichment_service.search_provider(
                        provider, work.title, author_names, edition.isbn
                    )
                else:
                    enriched = await enrichment_service.enrich(
                        work.title, author_names, edition.isbn, file_extension=file_ext
                    )

                if enriched:
                    changed = await _apply_enrichment(db, edition, work, enriched, force=force)
                    if changed:
                        await db.commit()
                        await db.refresh(work, ["authors", "contributors"])
                        await search_service.index_work(db, work, [a.name for a in work.authors])
                        await db.commit()
                else:
                    await db.rollback()

            except Exception as exc:
                logger.warning("Bulk enrich failed for edition %s: %s", edition_id, exc)
                job["failed"] += 1
                await db.rollback()

            job["done"] += 1

            # Broadcast progress every 5 books or on last
            if job["done"] % 5 == 0 or job["done"] == total:
                await broadcaster.enrich_progress(
                    job_id, job["done"], total, work.title, "running"
                )

            # Brief yield to not starve other tasks
            await asyncio.sleep(0.05)

    job["status"] = "done" if job.get("status") != "cancelled" else "cancelled"
    job["current"] = ""
    await broadcaster.enrich_progress(job_id, job["done"], total, "", job["status"])


@router.get("/backup")
async def download_backup(_admin: User = Depends(_require_admin)):
    """Download a tar.gz archive containing the database and config directory.

    The archive is streamed directly — no temp files needed.
    """
    settings = get_settings()
    config_path = Path(settings.CONFIG_PATH)
    db_path = config_path / "scriptorium.db"

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        # Add database file
        if db_path.exists():
            tar.add(db_path, arcname="backup/scriptorium.db")

        # Add any .env / config files in config dir (skip db itself)
        if config_path.exists():
            for f in config_path.iterdir():
                if f.is_file() and f.suffix in (".env", ".json", ".yaml", ".yml", ".toml"):
                    tar.add(f, arcname=f"backup/config/{f.name}")

    buf.seek(0)

    from datetime import datetime
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    return StreamingResponse(
        buf,
        media_type="application/gzip",
        headers={"Content-Disposition": f'attachment; filename="scriptorium_backup_{stamp}.tar.gz"'},
    )
