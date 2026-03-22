import asyncio
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from pydantic import BaseModel

from app.api.auth import get_current_user
from app.database import get_db, _session_factory
from app.models import User
from app.models.book import Book
from app.models.work import Work
from app.schemas.book import BookRead
from app.services.background_jobs import create_job, get_job, get_active_job, update_job, get_job_status

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/duplicates", tags=["duplicates"])


@router.get("/isbn", response_model=list[list[BookRead]])
async def find_isbn_duplicates(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Find books sharing the same ISBN (non-null). Returns groups of duplicates."""
    # Find ISBNs that appear more than once
    dup_result = await db.execute(
        select(Book.isbn)
        .where(Book.isbn.isnot(None))
        .group_by(Book.isbn)
        .having(func.count(Book.id) > 1)
    )
    dup_isbns = [row[0] for row in dup_result.all()]

    if not dup_isbns:
        return []

    groups = []
    for isbn in dup_isbns:
        books_result = await db.execute(
            select(Book)
            .options(
                joinedload(Book.work).options(
                    joinedload(Work.authors),
                    joinedload(Work.tags),
                    joinedload(Work.series),
                    joinedload(Work.contributors),
                ),
                joinedload(Book.files),
                joinedload(Book.contributors),
                joinedload(Book.location_ref),
            )
            .where(Book.isbn == isbn)
            .order_by(Book.created_at)
        )
        books = books_result.unique().scalars().all()
        groups.append([BookRead.model_validate(b) for b in books])

    return groups


@router.get("/title-author", response_model=list[list[BookRead]])
async def find_title_author_duplicates(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Find books with the exact same normalised title that share an author."""
    from sqlalchemy import and_
    from app.models.book import book_authors

    # Find normalised titles appearing more than once
    dup_result = await db.execute(
        select(func.lower(func.trim(Book.title)).label("norm_title"))
        .group_by(func.lower(func.trim(Book.title)))
        .having(func.count(Book.id) > 1)
    )
    dup_titles = [row[0] for row in dup_result.all()]

    if not dup_titles:
        return []

    groups = []
    for norm_title in dup_titles:
        books_result = await db.execute(
            select(Book)
            .options(
                joinedload(Book.work).options(
                    joinedload(Work.authors),
                    joinedload(Work.tags),
                    joinedload(Work.series),
                    joinedload(Work.contributors),
                ),
                joinedload(Book.files),
                joinedload(Book.contributors),
                joinedload(Book.location_ref),
            )
            .where(func.lower(func.trim(Book.title)) == norm_title)
            .order_by(Book.created_at)
        )
        books = books_result.unique().scalars().all()
        if len(books) > 1:
            # Only report as duplicates if they share at least one author
            author_sets = [set(a.id for a in b.authors) for b in books]
            has_shared_author = any(
                author_sets[i] & author_sets[j]
                for i in range(len(author_sets))
                for j in range(i + 1, len(author_sets))
            )
            if has_shared_author or all(len(s) == 0 for s in author_sets):
                groups.append([BookRead.model_validate(b) for b in books])

    return groups


class ConsolidateRequest(BaseModel):
    primary_id: int
    source_ids: list[int]


def _book_options():
    """Standard joinedload options for Book queries."""
    return [
        joinedload(Book.work).options(
            joinedload(Work.authors),
            joinedload(Work.tags),
            joinedload(Work.series),
            joinedload(Work.contributors),
        ),
        joinedload(Book.files),
        joinedload(Book.contributors),
        joinedload(Book.location_ref),
    ]


async def _consolidate_editions(db: AsyncSession, primary_id: int, source_ids: list[int]) -> None:
    """Merge source editions into primary: moves files, user data, deletes sources.

    Operates within the caller's session — caller must commit.
    """
    # Load primary to get work_id
    primary_result = await db.execute(select(Book).where(Book.id == primary_id))
    primary = primary_result.scalar_one_or_none()
    if not primary:
        return
    primary_work_id = primary.work_id

    for src_id in source_ids:
        if src_id == primary_id:
            continue

        src_result = await db.execute(select(Book).where(Book.id == src_id))
        src_edition = src_result.scalar_one_or_none()
        if not src_edition:
            continue
        src_work_id = src_edition.work_id

        # Move work-level data if different works
        if src_work_id and primary_work_id and src_work_id != primary_work_id:
            for tbl in ("shelf_books", "collection_books", "read_sessions"):
                await db.execute(
                    text(f"UPDATE OR IGNORE {tbl} SET work_id = :primary WHERE work_id = :src"),
                    {"primary": primary_work_id, "src": src_work_id},
                )
                await db.execute(text(f"DELETE FROM {tbl} WHERE work_id = :src"), {"src": src_work_id})

        # Move files
        await db.execute(
            text("UPDATE OR IGNORE edition_files SET edition_id = :primary WHERE edition_id = :src"),
            {"primary": primary_id, "src": src_id},
        )
        await db.execute(text("DELETE FROM edition_files WHERE edition_id = :src"), {"src": src_id})

        # Move edition-level data
        for tbl in ("annotations", "marginalia", "user_editions", "edition_contributors",
                     "kobo_book_states", "kobo_bookmarks", "kobo_synced_books"):
            await db.execute(
                text(f"UPDATE OR IGNORE {tbl} SET edition_id = :primary WHERE edition_id = :src"),
                {"primary": primary_id, "src": src_id},
            )

        # Read progress — special handling for user uniqueness
        await db.execute(
            text(
                "UPDATE OR IGNORE read_progress SET edition_id = :primary WHERE edition_id = :src "
                "AND NOT EXISTS (SELECT 1 FROM read_progress rp2 WHERE rp2.edition_id = :primary AND rp2.user_id = read_progress.user_id)"
            ),
            {"primary": primary_id, "src": src_id},
        )

        # Clean up any remaining references
        for tbl in ("annotations", "marginalia", "read_progress", "user_editions",
                     "edition_contributors", "kobo_book_states", "kobo_bookmarks", "kobo_synced_books"):
            await db.execute(text(f"DELETE FROM {tbl} WHERE edition_id = :src"), {"src": src_id})

        # Delete source edition
        await db.execute(text("DELETE FROM editions WHERE id = :src"), {"src": src_id})

        # Delete orphaned work
        if src_work_id and src_work_id != primary_work_id:
            orphan_check = await db.execute(
                text("SELECT COUNT(*) FROM editions WHERE work_id = :wid"),
                {"wid": src_work_id},
            )
            if orphan_check.scalar() == 0:
                for assoc in ("work_authors", "work_tags", "work_series", "work_contributors"):
                    await db.execute(text(f"DELETE FROM {assoc} WHERE work_id = :wid"), {"wid": src_work_id})
                await db.execute(text("DELETE FROM works WHERE id = :wid"), {"wid": src_work_id})


@router.post("/consolidate", response_model=BookRead)
async def consolidate_duplicates(
    data: ConsolidateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Merge source books into primary: moves all user data, deletes sources.
    Admin only — destructive operation."""
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")

    # Verify primary exists
    primary_result = await db.execute(
        select(Book).options(*_book_options()).where(Book.id == data.primary_id)
    )
    primary = primary_result.unique().scalar_one_or_none()
    if not primary:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Primary book not found")

    await _consolidate_editions(db, data.primary_id, data.source_ids)
    await db.commit()

    # Re-fetch and re-index
    fresh_result = await db.execute(
        select(Book).options(*_book_options()).where(Book.id == data.primary_id)
    )
    primary = fresh_result.unique().scalar_one()

    from app.services.search import search_service
    await search_service.index_book(db, primary, [a.name for a in primary.authors])
    await db.commit()

    return BookRead.model_validate(primary)


# ── Bulk Consolidation ──────────────────────────────────────────────────────

# Format preference for picking primary edition (lower = preferred)
_FORMAT_PRIORITY = {"epub": 0, "pdf": 1, "azw3": 2, "mobi": 3, "cbx": 4}


def _pick_primary(editions: list[dict]) -> tuple[int, list[int]]:
    """Pick the best primary edition from a group of duplicates.

    Prefers: epub > pdf > azw3 > mobi > cbx, then richest metadata
    (has ISBN, has cover, has description), then lowest ID (oldest).
    """
    def score(ed):
        fmt_score = _FORMAT_PRIORITY.get(ed["format"], 99)
        meta_score = -(
            (1 if ed["isbn"] else 0)
            + (1 if ed["cover_hash"] else 0)
            + (1 if ed["description"] else 0)
        )
        return (fmt_score, meta_score, ed["id"])

    ranked = sorted(editions, key=score)
    primary = ranked[0]["id"]
    sources = [e["id"] for e in ranked[1:]]
    return primary, sources


@router.get("/bulk/preview")
async def preview_bulk_consolidation(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Preview what bulk consolidation would do. Returns groups with chosen primary."""
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")

    groups = await _find_duplicate_groups(db)

    preview = []
    for group in groups:
        primary_id, source_ids = _pick_primary(group)
        primary_ed = next(e for e in group if e["id"] == primary_id)
        preview.append({
            "primary": primary_ed,
            "sources": [e for e in group if e["id"] in source_ids],
        })

    return {
        "total_groups": len(preview),
        "total_editions_to_remove": sum(len(g["sources"]) for g in preview),
        "groups": preview,
    }


@router.post("/bulk/consolidate")
async def start_bulk_consolidation(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Auto-consolidate all detected duplicate groups. Background job."""
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")

    groups = await _find_duplicate_groups(db)

    # Build consolidation plan: [(primary_id, [source_ids]), ...]
    plan = [_pick_primary(group) for group in groups]

    job_id, _ = await create_job(
        "bulk_consolidate",
        len(plan),
        {"consolidated": 0, "skipped": 0},
    )

    background_tasks.add_task(_run_bulk_consolidation, job_id, plan)
    return {
        "job_id": job_id,
        "total_groups": len(plan),
        "total_editions_to_remove": sum(len(sources) for _, sources in plan),
    }


@router.get("/bulk/consolidate/active")
async def get_active_consolidation_job(
    current_user: User = Depends(get_current_user),
):
    """Return the currently running/queued bulk consolidation job, if any."""
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    result = await get_active_job("bulk_consolidate")
    if result:
        job_id, job = result
        return {"job_id": job_id, **job}
    return None


@router.get("/bulk/consolidate/{job_id}")
async def get_bulk_consolidation_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
):
    """Poll bulk consolidation job status."""
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": job_id, **job}


async def _find_duplicate_groups(db: AsyncSession) -> list[list[dict]]:
    """Find editions with exact same title (case-insensitive) across different works.

    Returns list of groups, where each group is a list of edition dicts.
    """
    from app.models.edition import EditionFile

    # Get all editions with their work title, format, and metadata
    result = await db.execute(
        select(
            Book.id,
            Book.work_id,
            Work.title,
            Work.description,
            Book.isbn,
            Book.cover_hash,
            EditionFile.format,
        )
        .join(Book.work)
        .join(Book.files)
        .order_by(Work.title, Book.id)
    )
    rows = result.all()

    # Group by normalized title — one entry per edition (pick first file format)
    from collections import defaultdict
    edition_map = {}  # edition_id -> dict
    title_groups = defaultdict(list)

    for eid, wid, title, description, isbn, cover_hash, fmt in rows:
        if eid in edition_map:
            continue  # already seen (multiple files)
        norm_title = (title or "").lower().strip()
        ed = {
            "id": eid,
            "work_id": wid,
            "title": title,
            "description": description,
            "isbn": isbn,
            "cover_hash": cover_hash,
            "format": fmt,
        }
        edition_map[eid] = ed
        title_groups[norm_title].append(ed)

    # Filter to groups with multiple works
    groups = []
    for norm_title, editions in title_groups.items():
        work_ids = set(e["work_id"] for e in editions)
        if len(work_ids) > 1:
            groups.append(editions)

    return groups


async def _run_bulk_consolidation(
    job_id: str,
    plan: list[tuple[int, list[int]]],
) -> None:
    """Background task: consolidate each duplicate group."""
    from app.services.search import search_service

    await update_job(job_id, status="running")
    done = 0
    failed = 0
    consolidated = 0
    skipped = 0

    for primary_id, source_ids in plan:
        if await get_job_status(job_id) == "cancelled":
            break

        try:
            async with _session_factory() as db:
                # Verify primary still exists
                result = await db.execute(select(Book).where(Book.id == primary_id))
                primary = result.scalar_one_or_none()
                if not primary:
                    skipped += 1
                    done += 1
                    continue

                await _consolidate_editions(db, primary_id, source_ids)

                # Re-index FTS for primary
                result = await db.execute(
                    select(Book).options(*_book_options()).where(Book.id == primary_id)
                )
                primary = result.unique().scalar_one_or_none()
                if primary:
                    await search_service.index_book(db, primary, [a.name for a in primary.authors])

                await db.commit()
                consolidated += 1

        except Exception as exc:
            logger.warning("Bulk consolidation failed for primary %d: %s", primary_id, exc)
            failed += 1

        done += 1
        await update_job(
            job_id, done=done, failed=failed,
            consolidated=consolidated, skipped=skipped,
            current=f"Group {done}/{len(plan)}",
        )
        await asyncio.sleep(0.05)

    final_status = "done" if await get_job_status(job_id) != "cancelled" else "cancelled"
    await update_job(job_id, status=final_status, done=done, failed=failed,
                     consolidated=consolidated, skipped=skipped, current="")
