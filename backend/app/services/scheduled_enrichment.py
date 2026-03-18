"""Scheduled metadata refresh — periodically re-enrich books with gaps."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import joinedload

logger = logging.getLogger(__name__)

# In-memory state for the scheduler
_scheduler_task: Optional[asyncio.Task] = None
_scheduler_config = {
    "enabled": False,
    "interval_hours": 24,
    "last_run": None,
    "last_result": None,
}


async def _run_enrichment_cycle():
    """One cycle: find books with gaps and enrich them."""
    from app.database import get_session_factory
    from app.models.edition import Edition
    from app.models.work import Work
    from app.services.metadata_enrichment import enrichment_service
    from app.api.books import _apply_enrichment

    factory = get_session_factory()
    enriched_count = 0
    checked = 0

    try:
        async with factory() as db:
            # Find editions missing key metadata (no description, no cover, no tags)
            stmt = (
                select(Edition)
                .join(Edition.work)
                .where(
                    or_(
                        Work.description.is_(None),
                        Work.description == "",
                        Edition.cover_hash.is_(None),
                        Edition.cover_hash == "",
                    )
                )
                .where(Edition.isbn.isnot(None), Edition.isbn != "")
                .options(
                    joinedload(Edition.work).options(
                        joinedload(Work.authors),
                        joinedload(Work.tags),
                    ),
                    joinedload(Edition.files),
                )
                .limit(50)  # Process max 50 per cycle
            )
            result = await db.execute(stmt)
            editions = result.unique().scalars().all()

        # Process outside the main session to avoid long locks
        for edition in editions:
            checked += 1
            try:
                work = edition.work
                author_names = [a.name for a in work.authors] if work.authors else []
                file_ext = f".{edition.files[0].format}" if edition.files else None

                enriched = await enrichment_service.enrich(
                    work.title, author_names, edition.isbn, file_extension=file_ext
                )
                if enriched:
                    async with factory() as db:
                        # Re-fetch inside session
                        ed = await db.get(Edition, edition.id)
                        if ed:
                            wk_result = await db.execute(
                                select(Work).where(Work.id == ed.work_id)
                                .options(joinedload(Work.authors), joinedload(Work.tags))
                            )
                            wk = wk_result.unique().scalar_one_or_none()
                            if wk:
                                changed = await _apply_enrichment(db, ed, wk, enriched, force=False)
                                if changed:
                                    await db.commit()
                                    enriched_count += 1

                # Rate limit
                await asyncio.sleep(2)

            except Exception as exc:
                logger.debug("Scheduled enrich failed for edition %d: %s", edition.id, exc)

    except Exception as exc:
        logger.error("Scheduled enrichment cycle error: %s", exc)

    _scheduler_config["last_run"] = datetime.utcnow().isoformat()
    _scheduler_config["last_result"] = f"checked={checked}, enriched={enriched_count}"
    logger.info("Scheduled enrichment: checked %d, enriched %d", checked, enriched_count)


async def _scheduler_loop():
    """Main scheduler loop — runs enrichment cycles at the configured interval."""
    while _scheduler_config["enabled"]:
        try:
            await _run_enrichment_cycle()
        except Exception as exc:
            logger.error("Scheduler loop error: %s", exc)

        hours = _scheduler_config.get("interval_hours", 24)
        await asyncio.sleep(hours * 3600)


def start_scheduler(interval_hours: int = 24):
    """Start the background enrichment scheduler."""
    global _scheduler_task
    if _scheduler_task and not _scheduler_task.done():
        return  # Already running

    _scheduler_config["enabled"] = True
    _scheduler_config["interval_hours"] = interval_hours
    _scheduler_task = asyncio.create_task(_scheduler_loop())
    logger.info("Scheduled enrichment started (every %dh)", interval_hours)


def stop_scheduler():
    """Stop the background enrichment scheduler."""
    global _scheduler_task
    _scheduler_config["enabled"] = False
    if _scheduler_task and not _scheduler_task.done():
        _scheduler_task.cancel()
    _scheduler_task = None
    logger.info("Scheduled enrichment stopped")


def get_scheduler_status() -> dict:
    """Return current scheduler status."""
    return {
        "enabled": _scheduler_config["enabled"],
        "interval_hours": _scheduler_config["interval_hours"],
        "last_run": _scheduler_config["last_run"],
        "last_result": _scheduler_config["last_result"],
        "running": _scheduler_task is not None and not _scheduler_task.done() if _scheduler_task else False,
    }
