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

from app.services.background_jobs import create_job, get_job, get_active_job, update_job, get_job_status

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin")


def _spawn_background_task(func, *args):
    """Spawn a background task in a dedicated thread.

    The function should be a regular (sync) function, not async.
    It should use sync_update_job/sync_get_job_status for DB access.
    """
    import threading

    def _run():
        try:
            func(*args)
        except Exception as e:
            logger.error("Background task failed: %s", e, exc_info=True)

    t = threading.Thread(target=_run, daemon=True)
    t.start()


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

    # Collect IDs only — the background task opens its own session
    edition_ids = [e.id for e in editions]

    job_id, _ = await create_job("bulk_enrich", len(editions), {"error": None})
    background_tasks.add_task(_run_bulk_enrich, job_id, edition_ids, opts.force, opts.provider)

    return {"job_id": job_id, "total": len(editions)}


@router.get("/enrich/bulk/active")
async def get_active_enrich_job(
    _admin: User = Depends(_require_admin),
):
    """Return the currently running/queued bulk enrichment job, if any."""
    result = await get_active_job("bulk_enrich")
    if result:
        job_id, job = result
        return {"job_id": job_id, **job}
    return None


@router.get("/enrich/bulk/{job_id}")
async def get_bulk_enrich_job(
    job_id: str,
    _admin: User = Depends(_require_admin),
):
    """Poll the status of a bulk-enrichment job."""
    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": job_id, **job}


@router.delete("/enrich/bulk/{job_id}", status_code=204)
async def cancel_bulk_enrich_job(
    job_id: str,
    _admin: User = Depends(_require_admin),
):
    """Mark a bulk-enrichment job as cancelled (best-effort)."""
    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] == "running":
        await update_job(job_id, status="cancelled")


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

    await update_job(job_id, status="running")
    total = len(edition_ids)
    done = 0
    failed = 0

    async with _session_factory() as db:
        for i, edition_id in enumerate(edition_ids):
            if await get_job_status(job_id) == "cancelled":
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
                failed += 1
                continue

            work = edition.work
            current_title = work.title

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
                failed += 1
                await db.rollback()

            done += 1
            await update_job(job_id, done=done, failed=failed, current=current_title)

            # Broadcast progress every 5 books or on last
            if done % 5 == 0 or done == total:
                await broadcaster.enrich_progress(
                    job_id, done, total, current_title, "running"
                )

            # Brief yield to not starve other tasks
            await asyncio.sleep(0.05)

    final_status = "done" if await get_job_status(job_id) != "cancelled" else "cancelled"
    await update_job(job_id, status=final_status, current="")
    await broadcaster.enrich_progress(job_id, done, total, "", final_status)


# ── Bulk Markdown Generation ──────────────────────────────────────────────────

@router.post("/markdown/bulk")
async def start_bulk_markdown(
    background_tasks: BackgroundTasks,
    library_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(_require_admin),
):
    """Generate cached markdown for all editions missing it.

    Skips audiobooks (ABS-only with no files) and comics (image-based).
    Returns a job_id for polling.
    """
    from sqlalchemy import select
    from app.models.edition import Edition, EditionFile
    from app.services.markdown import has_cached_markdown, _SKIP_FORMATS

    stmt = select(Edition).where(Edition.files.any())
    if library_id:
        stmt = stmt.where(Edition.library_id == library_id)

    result = await db.execute(stmt)
    editions = result.unique().scalars().all()

    # Filter to editions that need markdown
    edition_ids = []
    for ed in editions:
        if has_cached_markdown(ed.uuid):
            continue
        edition_ids.append(ed.id)

    job_id, _ = await create_job("markdown", len(edition_ids), {"skipped": 0})
    _spawn_background_task(_run_bulk_markdown, job_id, edition_ids)
    return {"job_id": job_id, "total": len(edition_ids)}


@router.get("/markdown/bulk/active")
async def get_active_markdown_job(
    _admin: User = Depends(_require_admin),
):
    """Return the currently running/queued markdown generation job, if any."""
    result = await get_active_job("markdown")
    if result:
        job_id, job = result
        return {"job_id": job_id, **job}
    return None


@router.get("/markdown/bulk/{job_id}")
async def get_bulk_markdown_job(
    job_id: str,
    _admin: User = Depends(_require_admin),
):
    """Poll the status of a bulk markdown generation job."""
    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": job_id, **job}


def _run_bulk_markdown(job_id: str, edition_ids: list[int]) -> None:
    """Background task (sync, runs in thread): generate markdown for each edition.

    Uses a thread pool for parallel processing (4 workers).
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from app.services.markdown import generate_markdown_sync
    from app.services.background_jobs import sync_update_job, sync_get_job_status

    WORKERS = 4

    sync_update_job(job_id, status="running")
    total = len(edition_ids)
    done = 0
    generated = 0
    failed = 0
    skipped = 0

    def _process_one(edition_id):
        try:
            md = generate_markdown_sync(edition_id)
            return ("generated" if md else "skipped", edition_id)
        except Exception as exc:
            logger.warning("Markdown failed for edition %d: %s", edition_id, exc)
            return ("failed", edition_id)

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(_process_one, eid): eid for eid in edition_ids}

        for future in as_completed(futures):
            status, eid = future.result()
            done += 1
            if status == "generated":
                generated += 1
            elif status == "skipped":
                skipped += 1
            else:
                failed += 1

            if done % 20 == 0 or done == total:
                if sync_get_job_status(job_id) == "cancelled":
                    pool.shutdown(wait=False, cancel_futures=True)
                    break
                sync_update_job(job_id, done=done, failed=failed,
                                skipped=skipped, generated=generated,
                                current=f"{done}/{total} ({generated} gen, {skipped} skip, {failed} fail)")

    final_status = "done" if sync_get_job_status(job_id) != "cancelled" else "cancelled"
    sync_update_job(job_id, status=final_status, done=done, generated=generated,
                    failed=failed, skipped=skipped, current="")


# ── Bulk Identifier Extraction ───────────────────────────────────────────────


class IdentifierBatchRequest(BaseModel):
    edition_ids: list[int]


@router.post("/identifiers/batch")
async def start_batch_identifier_extraction(
    req: IdentifierBatchRequest,
    background_tasks: BackgroundTasks,
    _admin: User = Depends(_require_admin),
):
    """Scan a specific set of books for ISBN/DOI.

    Accepts an array of edition IDs. Returns a job_id for polling.
    """
    job_id, _ = await create_job("identifiers", len(req.edition_ids), {"found_isbn": 0, "found_doi": 0})
    background_tasks.add_task(_run_bulk_identifiers, job_id, req.edition_ids)
    return {"job_id": job_id, "total": len(req.edition_ids)}


@router.post("/identifiers/bulk")
async def start_bulk_identifier_extraction(
    library_id: Optional[int] = None,
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(_require_admin),
):
    """Scan book files for ISBN/DOI and update editions missing them.

    Returns a job_id for polling.
    """
    from sqlalchemy import select, or_
    from sqlalchemy.orm import joinedload
    from app.models.edition import Edition
    from app.models.work import Work

    # Find editions missing ISBN or whose work is missing DOI, that have files
    # Skip editions already scanned in a previous run
    stmt = (
        select(Edition)
        .join(Edition.work)
        .where(Edition.files.any())
        .where(Edition.identifiers_scanned == False)
        .where(or_(Edition.isbn.is_(None), Work.doi.is_(None)))
    )
    if library_id:
        stmt = stmt.where(Edition.library_id == library_id)

    result = await db.execute(stmt)
    editions = result.unique().scalars().all()
    edition_ids = [e.id for e in editions]

    job_id, _ = await create_job("identifiers", len(edition_ids), {"found_isbn": 0, "found_doi": 0})
    background_tasks.add_task(_run_bulk_identifiers, job_id, edition_ids)
    return {"job_id": job_id, "total": len(edition_ids)}


@router.get("/identifiers/bulk/active")
async def get_active_identifier_job(
    _admin: User = Depends(_require_admin),
):
    """Return the currently running/queued identifier extraction job, if any."""
    result = await get_active_job("identifiers")
    if result:
        job_id, job = result
        return {"job_id": job_id, **job}
    return None


@router.get("/identifiers/bulk/{job_id}")
async def get_bulk_identifier_job(
    job_id: str,
    _admin: User = Depends(_require_admin),
):
    """Poll the status of a bulk identifier extraction job."""
    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": job_id, **job}


async def _run_bulk_identifiers(job_id: str, edition_ids: list[int]) -> None:
    """Background task: extract identifiers for each edition."""
    from app.services.identifier_extraction import extract_identifiers_for_edition

    await update_job(job_id, status="running")
    total = len(edition_ids)
    done = 0
    failed = 0
    found_isbn = 0
    found_doi = 0

    for edition_id in edition_ids:
        # Check cancellation every 10 items (avoids per-item DB read)
        if done % 10 == 0 and await get_job_status(job_id) == "cancelled":
            break

        try:
            ids = await extract_identifiers_for_edition(edition_id)
            if ids.get("isbn_13"):
                found_isbn += 1
            if ids.get("doi"):
                found_doi += 1
        except Exception as exc:
            logger.warning("Identifier extraction failed for edition %d: %s", edition_id, exc)
            failed += 1

        done += 1

        # Batch DB updates and cancel checks every 10 items (avoids per-item DB writes)
        if done % 10 == 0 or done == total:
            await update_job(job_id, done=done, failed=failed, found_isbn=found_isbn, found_doi=found_doi)
            try:
                from app.services.events import broadcaster
                await broadcaster.enrich_progress(
                    job_id, done, total, "", "running"
                )
            except Exception:
                pass

        # Brief yield — extraction itself provides natural throttling via file I/O
        await asyncio.sleep(0.2)

    final_status = "done" if await get_job_status(job_id) != "cancelled" else "cancelled"
    await update_job(job_id, status=final_status, current="")


# ── Filename Metadata Extraction ──────────────────────────────────────────────

@router.post("/filename-extract/bulk")
async def start_bulk_filename_extract(
    library_id: Optional[int] = None,
    min_confidence: str = Query("medium", pattern="^(low|medium|high)$"),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(_require_admin),
):
    """Extract title/author from filenames for books with missing metadata."""
    from sqlalchemy import select, or_
    from sqlalchemy.orm import joinedload
    from app.models.edition import Edition
    from app.models.work import Work

    # Find editions with missing title or no authors
    stmt = (
        select(Edition)
        .join(Edition.work)
        .where(Edition.files.any())
        .where(
            or_(
                Work.title.is_(None),
                Work.title == '',
                ~Work.authors.any(),
            )
        )
    )
    if library_id:
        stmt = stmt.where(Edition.library_id == library_id)

    result = await db.execute(stmt)
    edition_ids = [e.id for e in result.unique().scalars().all()]

    job_id, _ = await create_job("filename_extract", len(edition_ids), {"applied": 0, "skipped": 0})
    background_tasks.add_task(_run_filename_extract, job_id, edition_ids, min_confidence)
    return {"job_id": job_id, "total": len(edition_ids)}


@router.get("/filename-extract/bulk/{job_id}")
async def get_filename_extract_job(
    job_id: str,
    _admin: User = Depends(_require_admin),
):
    """Poll filename extraction job status."""
    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": job_id, **job}


async def _run_filename_extract(job_id: str, edition_ids: list[int], min_confidence: str) -> None:
    from app.services.filename_metadata import extract_and_apply

    await update_job(job_id, status="running")
    done = 0
    failed = 0
    applied = 0
    skipped = 0

    for edition_id in edition_ids:
        if done % 50 == 0 and await get_job_status(job_id) == "cancelled":
            break
        try:
            result = await extract_and_apply(edition_id, min_confidence)
            if result.get("status") == "applied":
                applied += 1
            else:
                skipped += 1
        except Exception:
            failed += 1
        done += 1

        # Batch DB updates every 50 items for this tight loop
        if done % 50 == 0:
            await update_job(job_id, done=done, failed=failed, applied=applied, skipped=skipped)

        await asyncio.sleep(0.02)

    final_status = "done" if await get_job_status(job_id) != "cancelled" else "cancelled"
    await update_job(job_id, status=final_status, done=done, failed=failed, applied=applied, skipped=skipped, current="")


# ── Bulk Esoteric Analysis Pipeline ──────────────────────────────────────────

class BulkEsotericRequest(BaseModel):
    library_id: Optional[int] = None
    run_computational: bool = True
    run_llm: bool = False
    llm_template_ids: list[int] = []  # Empty = all builtin templates


@router.post("/esoteric/bulk")
async def start_bulk_esoteric_analysis(
    request: BulkEsotericRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(_require_admin),
):
    """Run esoteric analysis pipeline on all esoteric-enabled books.

    Two phases:
    - Computational: Runs all 16 pattern-detection tools (fast, no API cost)
    - LLM: Runs selected templates through the configured LLM (slow, costs tokens)

    Books that already have a 'full' computational analysis are skipped.
    """
    from sqlalchemy import select, and_
    from app.models.edition import Edition
    from app.models.work import Work
    from app.models.analysis import ComputationalAnalysis

    # Find esoteric-enabled editions with extractable files
    stmt = (
        select(Edition.id)
        .join(Edition.work)
        .where(Work.esoteric_enabled == True)
        .where(Edition.files.any())
    )
    if request.library_id:
        stmt = stmt.where(Edition.library_id == request.library_id)

    result = await db.execute(stmt)
    all_ids = [r[0] for r in result.all()]

    # Skip editions that already have a full computational analysis
    if request.run_computational:
        already_done = set()
        done_result = await db.execute(
            select(ComputationalAnalysis.edition_id)
            .where(
                ComputationalAnalysis.analysis_type == "full",
                ComputationalAnalysis.status == "completed",
                ComputationalAnalysis.edition_id.in_(all_ids),
            )
        )
        already_done = {r[0] for r in done_result.all()}
        computational_ids = [eid for eid in all_ids if eid not in already_done]
    else:
        computational_ids = []

    total = len(computational_ids)
    if request.run_llm:
        total += len(all_ids)  # LLM runs on all, not just unskipped

    job_id, _ = await create_job("bulk_esoteric", total, {
        "computational_done": 0,
        "computational_total": len(computational_ids),
        "computational_skipped": len(already_done) if request.run_computational else 0,
        "llm_done": 0,
        "llm_total": len(all_ids) if request.run_llm else 0,
    })

    logger.info("Starting bulk esoteric background task: %d computational, %d LLM",
                len(computational_ids), len(all_ids) if request.run_llm else 0)
    _spawn_background_task(
        _run_bulk_esoteric, job_id, computational_ids,
        all_ids if request.run_llm else [],
        request.llm_template_ids,
    )

    return {
        "job_id": job_id,
        "total_books": len(all_ids),
        "computational_to_run": len(computational_ids),
        "computational_skipped": len(all_ids) - len(computational_ids),
        "llm_to_run": len(all_ids) if request.run_llm else 0,
    }


@router.get("/esoteric/bulk/active")
async def get_active_esoteric_job(
    _admin: User = Depends(_require_admin),
):
    result = await get_active_job("bulk_esoteric")
    if result:
        job_id, job = result
        return {"job_id": job_id, **job}
    return None


@router.get("/esoteric/bulk/{job_id}")
async def get_esoteric_job(
    job_id: str,
    _admin: User = Depends(_require_admin),
):
    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": job_id, **job}


def _run_bulk_esoteric(
    job_id: str,
    computational_ids: list[int],
    llm_ids: list[int],
    llm_template_ids: list[int],
) -> None:
    """Background task (sync, runs in thread): esoteric analysis pipeline."""
    import json
    import sqlite3
    from app.services.esoteric import run_full_esoteric_analysis, EsotericAnalysisConfig
    from app.services.esoteric_engine import run_esoteric_analysis_v2
    from app.services.markdown import has_cached_markdown, markdown_path_for
    from app.services.text_extraction import (
        _extract_epub_markdown_sync, _extract_pdf_pdfplumber_sync, optimize_for_llm,
    )
    from app.services.background_jobs import sync_update_job, sync_get_job_status, _get_sync_db_path
    from pathlib import Path

    sync_update_job(job_id, status="running")
    done = 0
    failed = 0
    comp_done = 0

    db_path = _get_sync_db_path()

    for edition_id in computational_ids:
        if done % 10 == 0 and sync_get_job_status(job_id) == "cancelled":
            break

        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            try:
                row = conn.execute("""
                    SELECT e.id, e.uuid, w.title, w.id as work_id
                    FROM editions e JOIN works w ON w.id = e.work_id
                    WHERE e.id = ?
                """, (edition_id,)).fetchone()
                if not row:
                    failed += 1
                    done += 1
                    continue

                logger.info("Esoteric %d/%d: edition %d (%s)",
                            done + 1, len(computational_ids), edition_id, row["title"][:50])

                # Get text — prefer cached markdown
                text = None
                if has_cached_markdown(row["uuid"]):
                    text = markdown_path_for(row["uuid"]).read_text(encoding="utf-8")
                else:
                    # Extract from file
                    frow = conn.execute("""
                        SELECT file_path, format FROM edition_files
                        WHERE edition_id = ? ORDER BY
                        CASE format WHEN 'epub' THEN 0 WHEN 'pdf' THEN 2 ELSE 5 END
                        LIMIT 1
                    """, (edition_id,)).fetchone()
                    if frow:
                        from app.config import resolve_path
                        fp = Path(resolve_path(frow["file_path"]))
                        fmt = frow["format"].lower()
                        if fp.exists():
                            if fmt == "epub":
                                text = _extract_epub_markdown_sync(fp)
                            elif fmt == "pdf":
                                text = _extract_pdf_pdfplumber_sync(fp)

                if not text or len(text.strip()) < 200:
                    done += 1
                    continue

                # Run analysis
                config = EsotericAnalysisConfig()
                v1_results = run_full_esoteric_analysis(text, config)
                v2_results = run_esoteric_analysis_v2(text)
                results = {**v1_results, "engine_v2": v2_results}

                # Save to DB
                conn.execute("""
                    INSERT INTO computational_analyses
                    (edition_id, analysis_type, config_json, results_json, status, created_at)
                    VALUES (?, 'full', ?, ?, 'completed', datetime('now'))
                """, (
                    edition_id,
                    json.dumps({"keywords": config.keywords}),
                    json.dumps(results, default=str),
                ))
                conn.commit()
                comp_done += 1
                score = v2_results.get("overall_score", "?")
                logger.info("Esoteric done: edition %d score=%s", edition_id, score)

            finally:
                conn.close()

        except Exception as exc:
            logger.warning("Esoteric failed for %d: %s", edition_id, exc)
            failed += 1

        done += 1
        sync_update_job(
            job_id, done=done, failed=failed,
            computational_done=comp_done,
            current=f"Computational {comp_done}/{len(computational_ids)}",
        )

    # Mark job done for computational phase
    final_status = "done" if sync_get_job_status(job_id) != "cancelled" else "cancelled"
    sync_update_job(job_id, status=final_status, current="")
    logger.info("Bulk esoteric computational complete: %d done, %d failed out of %d",
                comp_done, failed, len(computational_ids))

    # Phase 2: LLM analysis — TODO: rewrite as sync
    # Phase 3: EPUB export — TODO: rewrite as sync
    # TODO: Phase 2 (LLM) and Phase 3 (EPUB) need sync rewrite


# Dead async code removed — will be rewritten as sync



# ── LLM Metadata Extraction ──────────────────────────────────────────────────

@router.post("/llm-metadata/bulk")
async def start_bulk_llm_metadata(
    library_id: Optional[int] = None,
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(_require_admin),
):
    """Use LLM to extract metadata from book text for editions missing key fields.

    Targets editions that have extractable files (EPUB/PDF) but are missing
    title, authors, or description after all other extraction methods have been tried.
    """
    from sqlalchemy import select, or_
    from app.models.edition import Edition, EditionFile
    from app.models.work import Work

    stmt = (
        select(Edition)
        .join(Edition.work)
        .where(Edition.files.any(
            or_(EditionFile.format.ilike("epub"), EditionFile.format.ilike("pdf"))
        ))
        .where(
            or_(
                Work.description.is_(None),
                Work.description == "",
                ~Work.authors.any(),
            )
        )
    )
    if library_id:
        stmt = stmt.where(Edition.library_id == library_id)

    result = await db.execute(stmt)
    edition_ids = [e.id for e in result.unique().scalars().all()]

    job_id, _ = await create_job("llm_metadata", len(edition_ids), {
        "found_title": 0, "found_authors": 0, "found_description": 0,
        "found_publisher": 0, "found_isbn": 0,
    })
    background_tasks.add_task(_run_bulk_llm_metadata, job_id, edition_ids)
    return {"job_id": job_id, "total": len(edition_ids)}


@router.get("/llm-metadata/bulk/active")
async def get_active_llm_metadata_job(
    _admin: User = Depends(_require_admin),
):
    """Return active LLM metadata extraction job."""
    result = await get_active_job("llm_metadata")
    if result:
        job_id, job = result
        return {"job_id": job_id, **job}
    return None


@router.get("/llm-metadata/bulk/{job_id}")
async def get_llm_metadata_job(
    job_id: str,
    _admin: User = Depends(_require_admin),
):
    """Poll LLM metadata extraction job status."""
    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": job_id, **job}


async def _run_bulk_llm_metadata(job_id: str, edition_ids: list[int]) -> None:
    """Background task: extract metadata via LLM for each edition."""
    from app.services.llm_metadata import extract_llm_metadata_for_edition

    await update_job(job_id, status="running")
    total = len(edition_ids)
    done = 0
    failed = 0
    found_title = 0
    found_authors = 0
    found_description = 0
    found_publisher = 0
    found_isbn = 0

    for edition_id in edition_ids:
        if done % 5 == 0 and await get_job_status(job_id) == "cancelled":
            break

        try:
            found = await extract_llm_metadata_for_edition(edition_id)
            if found.get("title"):
                found_title += 1
            if found.get("authors"):
                found_authors += 1
            if found.get("description"):
                found_description += 1
            if found.get("publisher"):
                found_publisher += 1
            if found.get("isbn"):
                found_isbn += 1
        except Exception as exc:
            logger.warning("LLM metadata extraction failed for edition %d: %s", edition_id, exc)
            failed += 1

        done += 1

        if done % 5 == 0 or done == total:
            await update_job(
                job_id, done=done, failed=failed,
                found_title=found_title, found_authors=found_authors,
                found_description=found_description, found_publisher=found_publisher,
                found_isbn=found_isbn,
                current=f"{done}/{total}",
            )

        # LLM calls are rate-limited; brief pause between items
        await asyncio.sleep(1.0)

    final_status = "done" if await get_job_status(job_id) != "cancelled" else "cancelled"
    await update_job(
        job_id, status=final_status, done=done, failed=failed,
        found_title=found_title, found_authors=found_authors,
        found_description=found_description, found_publisher=found_publisher,
        found_isbn=found_isbn, current="",
    )


# ── Embedded Metadata Extraction (OPF / ComicInfo.xml) ───────────────────────

@router.post("/embedded-metadata/bulk")
async def start_bulk_embedded_metadata(
    library_id: Optional[int] = None,
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(_require_admin),
):
    """Scan EPUB/CBZ/CBR files for embedded metadata (OPF, ComicInfo.xml).

    Fills in missing ISBN, publisher, language, description, authors, and
    published date from the metadata already inside book files.
    """
    from sqlalchemy import select, or_
    from app.models.edition import Edition, EditionFile
    from app.models.work import Work

    stmt = (
        select(Edition)
        .join(Edition.work)
        .where(Edition.opf_scanned == False)
        .where(Edition.files.any(
            or_(
                EditionFile.format.ilike("epub"),
                EditionFile.format.ilike("cbz"),
                EditionFile.format.ilike("cbr"),
            )
        ))
    )
    if library_id:
        stmt = stmt.where(Edition.library_id == library_id)

    result = await db.execute(stmt)
    edition_ids = [e.id for e in result.unique().scalars().all()]

    job_id, _ = await create_job("embedded_metadata", len(edition_ids), {
        "found_isbn": 0, "found_publisher": 0, "found_language": 0,
        "found_description": 0, "found_authors": 0, "found_date": 0,
    })
    background_tasks.add_task(_run_bulk_embedded_metadata, job_id, edition_ids)
    return {"job_id": job_id, "total": len(edition_ids)}


@router.get("/embedded-metadata/bulk/active")
async def get_active_embedded_metadata_job(
    _admin: User = Depends(_require_admin),
):
    """Return active embedded metadata extraction job."""
    result = await get_active_job("embedded_metadata")
    if result:
        job_id, job = result
        return {"job_id": job_id, **job}
    return None


@router.get("/embedded-metadata/bulk/{job_id}")
async def get_embedded_metadata_job(
    job_id: str,
    _admin: User = Depends(_require_admin),
):
    """Poll embedded metadata extraction job status."""
    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": job_id, **job}


async def _run_bulk_embedded_metadata(job_id: str, edition_ids: list[int]) -> None:
    """Background task: extract embedded metadata from EPUB/CBZ/CBR files."""
    from app.services.opf_extraction import extract_embedded_metadata_for_edition

    await update_job(job_id, status="running")
    total = len(edition_ids)
    done = 0
    failed = 0
    found_isbn = 0
    found_publisher = 0
    found_language = 0
    found_description = 0
    found_authors = 0
    found_date = 0

    for edition_id in edition_ids:
        if await get_job_status(job_id) == "cancelled":
            break

        try:
            found = await extract_embedded_metadata_for_edition(edition_id)
            if found.get("isbn"):
                found_isbn += 1
            if found.get("publisher"):
                found_publisher += 1
            if found.get("language"):
                found_language += 1
            if found.get("description"):
                found_description += 1
            if found.get("authors"):
                found_authors += 1
            if found.get("date"):
                found_date += 1
        except Exception as exc:
            logger.warning("Embedded metadata extraction failed for edition %d: %s", edition_id, exc)
            failed += 1

        done += 1

        if done % 20 == 0 or done == total:
            await update_job(
                job_id, done=done, failed=failed,
                found_isbn=found_isbn, found_publisher=found_publisher,
                found_language=found_language, found_description=found_description,
                found_authors=found_authors, found_date=found_date,
                current=f"{done}/{total}",
            )

        await asyncio.sleep(0.1)

    final_status = "done" if await get_job_status(job_id) != "cancelled" else "cancelled"
    await update_job(
        job_id, status=final_status, done=done, failed=failed,
        found_isbn=found_isbn, found_publisher=found_publisher,
        found_language=found_language, found_description=found_description,
        found_authors=found_authors, found_date=found_date,
        current="",
    )


# ── Cover Quality & Upgrade ──────────────────────────────────────────────────

@router.get("/covers/low-quality")
async def list_low_quality_covers(
    library_id: Optional[int] = None,
    _admin: User = Depends(_require_admin),
):
    """Find editions with low-resolution or undersized covers."""
    from app.services.cover_quality import find_low_quality_covers
    return await find_low_quality_covers(library_id)


@router.post("/covers/upgrade")
async def start_cover_upgrade(
    library_id: Optional[int] = None,
    background_tasks: BackgroundTasks = None,
    _admin: User = Depends(_require_admin),
):
    """Find low-quality covers and attempt iTunes upgrade. Background job."""
    from app.services.cover_quality import find_low_quality_covers
    low = await find_low_quality_covers(library_id)
    edition_ids = [item["edition_id"] for item in low]

    job_id, _ = await create_job("cover_upgrade", len(edition_ids), {"upgraded": 0, "no_match": 0})
    background_tasks.add_task(_run_cover_upgrade, job_id, edition_ids)
    return {"job_id": job_id, "total": len(edition_ids)}


@router.get("/covers/upgrade/{job_id}")
async def get_cover_upgrade_job(
    job_id: str,
    _admin: User = Depends(_require_admin),
):
    """Poll cover upgrade job status."""
    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": job_id, **job}


async def _run_cover_upgrade(job_id: str, edition_ids: list[int]) -> None:
    """Background task: upgrade low-quality covers via iTunes."""
    from app.services.cover_quality import upgrade_cover

    await update_job(job_id, status="running")
    done = 0
    failed = 0
    upgraded = 0
    no_match = 0

    for edition_id in edition_ids:
        if await get_job_status(job_id) == "cancelled":
            break

        result = await upgrade_cover(edition_id)
        result_status = result.get("status", "failed")
        if result_status == "upgraded":
            upgraded += 1
        elif result_status == "no_match":
            no_match += 1
        else:
            failed += 1

        done += 1
        current_title = result.get("itunes_title") or result.get("title") or ""
        await update_job(job_id, done=done, failed=failed, upgraded=upgraded, no_match=no_match, current=current_title)

        # iTunes rate limiting (~20 req/min)
        await asyncio.sleep(3)

    final_status = "done" if await get_job_status(job_id) != "cancelled" else "cancelled"
    await update_job(job_id, status=final_status, current="")


# ── Bulk cover fetch (for books with no cover) ────────────────────────────────

@router.post("/covers/fetch")
async def start_cover_fetch(
    library_id: Optional[int] = None,
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(_require_admin),
):
    """Find books with no cover and attempt to fetch from enrichment providers."""
    from sqlalchemy import select
    from app.models.edition import Edition
    from app.models.work import Work

    stmt = (
        select(Edition.id)
        .where(
            (Edition.cover_hash.is_(None)) | (Edition.cover_hash == ""),
            (Edition.isbn.isnot(None)) & (Edition.isbn != ""),
        )
    )
    if library_id:
        stmt = stmt.where(Edition.library_id == library_id)
    result = await db.execute(stmt)
    edition_ids = [r[0] for r in result.all()]

    job_id, _ = await create_job("cover_fetch", len(edition_ids), {"found": 0, "not_found": 0})
    background_tasks.add_task(_run_cover_fetch, job_id, edition_ids)
    return {"job_id": job_id, "total": len(edition_ids)}


@router.get("/covers/fetch/{job_id}")
async def get_cover_fetch_job(
    job_id: str,
    _admin: User = Depends(_require_admin),
):
    """Poll cover fetch job status."""
    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": job_id, **job}


async def _run_cover_fetch(job_id: str, edition_ids: list[int]) -> None:
    """Background task: fetch covers for books that have none."""
    import httpx
    from sqlalchemy import select
    from sqlalchemy.orm import joinedload
    from app.models.edition import Edition
    from app.models.work import Work
    from app.services.covers import cover_service
    from app.services.metadata_enrichment import enrichment_service

    await update_job(job_id, status="running")
    done = 0
    failed = 0
    found = 0
    not_found = 0
    current_title = ""

    for edition_id in edition_ids:
        if await get_job_status(job_id) == "cancelled":
            break

        try:
            # Fresh session per book to avoid blocking other requests (SQLite)
            async with _session_factory() as db:
                result = await db.execute(
                    select(Edition)
                    .where(Edition.id == edition_id)
                    .options(joinedload(Edition.work).options(joinedload(Work.authors)))
                )
                edition = result.unique().scalar_one_or_none()
                if not edition or edition.cover_hash:
                    done += 1
                    await update_job(job_id, done=done)
                    continue

                work = edition.work
                current_title = work.title if work else f"Edition {edition_id}"
                isbn = edition.isbn
                book_uuid = edition.uuid
                author_names = [a.name for a in work.authors] if work else []

            # Do network I/O outside the DB session
            enriched = await enrichment_service.enrich(current_title, author_names, isbn)

            cover_url = enriched.get("cover_url") if enriched else None
            if cover_url:
                async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                    resp = await client.get(cover_url)
                    if resp.status_code == 200 and resp.content and len(resp.content) > 1000:
                        cover_hash, cover_format, cover_color = await cover_service.save_cover(
                            resp.content, book_uuid
                        )
                        if cover_hash:
                            async with _session_factory() as db:
                                edition = await db.get(Edition, edition_id)
                                if edition:
                                    edition.cover_hash = cover_hash
                                    edition.cover_format = cover_format
                                    edition.cover_color = cover_color
                                    await db.commit()
                            found += 1
                        else:
                            not_found += 1
                    else:
                        not_found += 1
            else:
                not_found += 1

        except Exception as exc:
            logger.warning("Cover fetch failed for edition %d: %s", edition_id, exc)
            failed += 1

        done += 1
        await update_job(job_id, done=done, failed=failed, found=found, not_found=not_found, current=current_title)
        # Rate limit — ~1 req/sec to be polite to APIs
        await asyncio.sleep(1)

    final_status = "done" if await get_job_status(job_id) != "cancelled" else "cancelled"
    await update_job(job_id, status=final_status, current="")


# ── Audit Log ──────────────────────────────────────────────────────────────────

@router.get("/audit-log")
async def get_audit_log(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    action: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(_require_admin),
):
    """Retrieve recent audit log entries."""
    from sqlalchemy import select
    from app.models.audit import AuditLog

    stmt = select(AuditLog).order_by(AuditLog.created_at.desc())
    if action:
        stmt = stmt.where(AuditLog.action.ilike(f"%{action}%"))
    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    entries = result.scalars().all()
    return [
        {
            "id": e.id,
            "user_id": e.user_id,
            "action": e.action,
            "entity_type": e.entity_type,
            "entity_id": e.entity_id,
            "detail": e.detail,
            "ip_address": e.ip_address,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in entries
    ]


# ── Scheduled Enrichment ────────────────────────────────────────────────────────

@router.get("/scheduler/status")
async def get_scheduler_status(_admin: User = Depends(_require_admin)):
    from app.services.scheduled_enrichment import get_scheduler_status
    return get_scheduler_status()


@router.post("/scheduler/start")
async def start_scheduler(
    interval_hours: int = Query(24, ge=1, le=168),
    _admin: User = Depends(_require_admin),
):
    from app.services.scheduled_enrichment import start_scheduler
    start_scheduler(interval_hours)
    return {"status": "started", "interval_hours": interval_hours}


@router.post("/scheduler/stop")
async def stop_scheduler(_admin: User = Depends(_require_admin)):
    from app.services.scheduled_enrichment import stop_scheduler
    stop_scheduler()
    return {"status": "stopped"}


@router.post("/scheduler/run-now")
async def run_scheduler_now(
    background_tasks: BackgroundTasks = None,
    _admin: User = Depends(_require_admin),
):
    from app.services.scheduled_enrichment import _run_enrichment_cycle
    background_tasks.add_task(_run_enrichment_cycle)
    return {"status": "triggered"}


# ── Page Hash Duplicate Detection ──────────────────────────────────────────────

@router.get("/comics/duplicates/{edition_id}")
async def find_duplicate_pages_in_file(
    edition_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(_require_admin),
):
    """Find duplicate pages within a single comic file."""
    from sqlalchemy import select
    from app.models.edition import EditionFile
    ef = (await db.execute(
        select(EditionFile).where(EditionFile.edition_id == edition_id, EditionFile.format == "cbz")
    )).scalar_one_or_none()
    if not ef:
        raise HTTPException(status_code=404, detail="No CBZ file found")

    from app.services.page_hash import find_duplicate_pages
    dupes = find_duplicate_pages(ef.file_path)
    return {"edition_id": edition_id, "duplicates": dupes}


@router.post("/comics/duplicates/cross-file")
async def find_cross_file_duplicate_pages(
    edition_ids: list[int],
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(_require_admin),
):
    """Find pages that appear across multiple comic files."""
    from app.services.page_hash import find_cross_file_duplicates
    dupes = await find_cross_file_duplicates(edition_ids, db)
    return {"edition_count": len(edition_ids), "cross_duplicates": dupes}


# ── Split Edition (fix multi-file editions) ────────────────────────────────────

@router.post("/editions/{edition_id}/split")
async def split_edition(
    edition_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(_require_admin),
):
    """Split an edition with multiple files into separate works/editions.

    Each file gets its own Work + Edition based on the title extracted from
    the filename. The original edition keeps the first file; new editions
    are created for the rest. Authors and library are inherited.
    """
    import re
    import uuid as _uuid
    from datetime import datetime
    from sqlalchemy import select
    from sqlalchemy.orm import joinedload
    from app.models.edition import Edition, EditionFile
    from app.models.work import Work

    result = await db.execute(
        select(Edition)
        .where(Edition.id == edition_id)
        .options(
            joinedload(Edition.files),
            joinedload(Edition.work).options(joinedload(Work.authors)),
        )
    )
    edition = result.unique().scalar_one_or_none()
    if not edition:
        raise HTTPException(status_code=404, detail="Edition not found")

    files = list(edition.files)
    if len(files) <= 1:
        return {"status": "nothing_to_split", "files": len(files)}

    work = edition.work
    authors = list(work.authors) if work.authors else []

    def guess_title(filename: str) -> str:
        stem = filename.rsplit(".", 1)[0] if "." in filename else filename
        # Remove common noise: hash, "Anna's Archive", year in parens, etc.
        stem = re.sub(r"\s*--\s*.*$", "", stem)  # strip everything after " -- "
        stem = re.sub(r"\s*-\s*[A-Z][a-z]+\s+[A-Z].*$", "", stem)  # " - Author Name"
        stem = re.sub(r"\s*\([^)]*\)\s*$", "", stem)  # trailing (year) or (edition)
        stem = re.sub(r"[_]+", " ", stem)
        return stem.strip() or filename

    # Keep the first file on the original edition; split the rest
    keep_file = files[0]
    split_files = files[1:]

    created = []
    for ef in split_files:
        title = guess_title(ef.filename)

        # Create new Work
        new_uuid = str(_uuid.uuid4())
        new_work = Work(
            uuid=new_uuid,
            title=title,
            language=work.language,
            authors=authors,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(new_work)
        await db.flush()

        # Create new Edition
        new_edition = Edition(
            uuid=new_uuid,
            work_id=new_work.id,
            library_id=edition.library_id,
            format=ef.format,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(new_edition)
        await db.flush()

        # Move the file to the new edition
        ef.edition_id = new_edition.id
        created.append({"edition_id": new_edition.id, "title": title, "file": ef.filename})

    await db.commit()

    return {
        "status": "split",
        "original_edition": edition_id,
        "kept_file": keep_file.filename,
        "created": created,
        "total_split": len(created),
    }


@router.post("/editions/split-all")
async def split_all_bloated_editions(
    min_files: int = Query(3, ge=2, le=100),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(_require_admin),
):
    """Find all editions with more than min_files and split them.

    Returns the list of edition IDs that will be processed.
    """
    from sqlalchemy import select, func
    from app.models.edition import Edition, EditionFile

    stmt = (
        select(Edition.id, func.count(EditionFile.id).label("cnt"))
        .join(EditionFile, EditionFile.edition_id == Edition.id)
        .group_by(Edition.id)
        .having(func.count(EditionFile.id) >= min_files)
        .order_by(func.count(EditionFile.id).desc())
    )
    result = await db.execute(stmt)
    edition_ids = [(r[0], r[1]) for r in result.all()]

    async def _run_splits():
        from app.database import _session_factory
        for eid, cnt in edition_ids:
            try:
                async with _session_factory() as sdb:
                    # Re-use the split logic inline
                    import re
                    import uuid as _uuid2
                    from datetime import datetime as _dt
                    from sqlalchemy.orm import joinedload as _jl
                    from app.models.edition import Edition as _Ed, EditionFile as _EF
                    from app.models.work import Work as _Wk

                    res = await sdb.execute(
                        select(_Ed).where(_Ed.id == eid)
                        .options(_jl(_Ed.files), _jl(_Ed.work).options(_jl(_Wk.authors)))
                    )
                    ed = res.unique().scalar_one_or_none()
                    if not ed or len(ed.files) <= 1:
                        continue

                    wk = ed.work
                    authors = list(wk.authors) if wk.authors else []
                    files = list(ed.files)

                    for ef in files[1:]:
                        stem = ef.filename.rsplit(".", 1)[0] if "." in ef.filename else ef.filename
                        title = re.sub(r"\s*--\s*.*$", "", stem)
                        title = re.sub(r"\s*-\s*[A-Z][a-z]+\s+[A-Z].*$", "", title)
                        title = re.sub(r"\s*\([^)]*\)\s*$", "", title)
                        title = title.strip() or ef.filename

                        new_uuid = str(_uuid2.uuid4())
                        nw = _Wk(uuid=new_uuid, title=title, language=wk.language,
                                 authors=authors, created_at=_dt.utcnow(), updated_at=_dt.utcnow())
                        sdb.add(nw)
                        await sdb.flush()
                        ne = _Ed(uuid=new_uuid, work_id=nw.id, library_id=ed.library_id,
                                 format=ef.format, created_at=_dt.utcnow(), updated_at=_dt.utcnow())
                        sdb.add(ne)
                        await sdb.flush()
                        ef.edition_id = ne.id

                    await sdb.commit()
                    logger.info("Split edition %d: %d files → %d new editions", eid, cnt, cnt - 1)
            except Exception as exc:
                logger.warning("Failed to split edition %d: %s", eid, exc)

    background_tasks.add_task(_run_splits)
    return {
        "status": "queued",
        "editions_to_split": len(edition_ids),
        "details": [{"edition_id": eid, "file_count": cnt} for eid, cnt in edition_ids[:20]],
    }


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
