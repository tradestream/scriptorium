"""Reading statistics — aggregated from ReadingState + EditionPosition + ReadSession + KoboBookState."""

from collections import Counter
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api.auth import get_current_user
from app.database import get_db
from app.models import User
from app.models.edition import Edition
from app.models.progress import KoboBookState
from app.models.read_session import ReadSession
from app.models.work import Work

router = APIRouter(prefix="/stats", tags=["stats"])


class _BookProgress(BaseModel):
    id: int
    title: str
    author: Optional[str] = None
    percentage: float
    last_opened: Optional[str] = None


class _BookCompleted(BaseModel):
    id: int
    title: str
    author: Optional[str] = None
    completed_at: Optional[str] = None
    rating: Optional[int] = None


class _Session(BaseModel):
    id: int
    book_id: int
    title: str
    author: Optional[str] = None
    started_at: str
    finished_at: Optional[str] = None
    rating: Optional[int] = None
    notes: Optional[str] = None


class ReadingStats(BaseModel):
    # Core counts
    total_books: int
    books_reading: int
    books_completed: int
    books_abandoned: int
    pages_read: int
    time_reading_seconds: int
    sessions_this_year: int

    # Detailed lists
    currently_reading: list[_BookProgress]
    recently_completed: list[_BookCompleted]
    recent_sessions: list[_Session]

    # Booklore-style enrichments
    completions_by_month: list[dict]   # [{"month": "2025-03", "count": int}]
    activity_by_day: list[dict]        # [{"date": "2025-03-14", "count": int}]
    current_streak: int
    longest_streak: int
    avg_rating: Optional[float] = None
    rating_distribution: dict[str, int]  # "1".."5" → count

    # BookLore-inspired analytics
    peak_hours: list[dict] = []         # [{"hour": 0-23, "count": int}]
    day_of_week: list[dict] = []        # [{"day": "Mon".."Sun", "count": int}]
    reading_speed: Optional[dict] = None  # {"pages_per_hour": float, "books_sampled": int}
    time_by_month: list[dict] = []      # [{"month": "2025-03", "seconds": int}]
    top_genres: list[dict] = []         # [{"tag": str, "count": int}]


@router.get("", response_model=ReadingStats)
async def get_reading_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return reading statistics for the current user."""
    from app.models.reading import EditionPosition, ReadingState

    # ── ReadingState records (canonical per-user, per-work lifecycle) ────────
    # Plus one display Edition per work (any will do; pick the lowest id for
    # determinism) and the EditionPosition with the freshest activity for
    # percentage / pages-read calculations.
    rs_rows = (
        await db.execute(
            select(ReadingState).where(ReadingState.user_id == current_user.id)
        )
    ).scalars().all()
    work_ids = [rs.work_id for rs in rs_rows]

    work_to_edition: dict[int, Edition] = {}
    if work_ids:
        ed_rows = (
            await db.execute(
                select(Edition)
                .where(Edition.work_id.in_(work_ids))
                .options(
                    joinedload(Edition.work).options(
                        joinedload(Work.authors), joinedload(Work.tags)
                    )
                )
                .order_by(Edition.id)
            )
        ).unique().scalars().all()
        for e in ed_rows:
            work_to_edition.setdefault(e.work_id, e)

    work_to_pct: dict[int, float] = {}
    work_to_pages: dict[int, Optional[int]] = {}
    if work_ids:
        ep_rows = (
            await db.execute(
                select(EditionPosition).where(
                    EditionPosition.user_id == current_user.id
                )
            )
        ).scalars().all()
        for ep in ep_rows:
            ed = next(
                (e for e in work_to_edition.values() if e.id == ep.edition_id), None
            )
            if ed is None:
                continue
            wid = ed.work_id
            # Prefer the freshest EditionPosition for percentage display.
            stamp = ep.current_updated_at or ep.updated_at
            existing_stamp = work_to_pct.get(f"_stamp_{wid}")  # type: ignore[arg-type]
            if existing_stamp is None or (stamp and stamp > existing_stamp):
                work_to_pct[wid] = (ep.current_pct or 0.0) * 100.0
                work_to_pct[f"_stamp_{wid}"] = stamp  # type: ignore[assignment]
                if ep.total_pages is not None:
                    work_to_pages[wid] = ep.total_pages

    # ── Sessions ─────────────────────────────────────────────────────────────
    sess_result = await db.execute(
        select(ReadSession)
        .where(ReadSession.user_id == current_user.id)
        .options(joinedload(ReadSession.work).options(joinedload(Work.authors)))
        .order_by(ReadSession.started_at.desc())
    )
    sessions = sess_result.unique().scalars().all()

    # ── Kobo reading time ────────────────────────────────────────────────────
    kobo_result = await db.execute(
        select(KoboBookState).where(KoboBookState.user_id == current_user.id)
    )
    kobo_states = kobo_result.scalars().all()
    time_reading_seconds = sum(k.time_spent_reading for k in kobo_states)

    # ── Basic counts ─────────────────────────────────────────────────────────
    status_counter: Counter = Counter(rs.status for rs in rs_rows)
    pages_read = 0
    for rs in rs_rows:
        pct = work_to_pct.get(rs.work_id, 0.0)
        pages = work_to_pages.get(rs.work_id)
        if pages:
            pages_read += int(round((pct / 100.0) * pages))

    now = datetime.utcnow()
    year_start = datetime(now.year, 1, 1)
    sessions_this_year = sum(1 for s in sessions if s.started_at >= year_start)

    # ── Helper accessors ─────────────────────────────────────────────────────
    def _rs_author(rs: ReadingState) -> Optional[str]:
        ed = work_to_edition.get(rs.work_id)
        if ed is None:
            return None
        try:
            authors = ed.work.authors
            return authors[0].name if authors else None
        except Exception:
            return None

    def _rs_title(rs: ReadingState) -> str:
        ed = work_to_edition.get(rs.work_id)
        if ed is None:
            return f"Work {rs.work_id}"
        try:
            return ed.work.title
        except Exception:
            return f"Work {rs.work_id}"

    def _rs_display_edition_id(rs: ReadingState) -> int:
        ed = work_to_edition.get(rs.work_id)
        return ed.id if ed else rs.work_id

    def _sess_author(s: ReadSession) -> Optional[str]:
        try:
            authors = s.work.authors
            return authors[0].name if authors else None
        except Exception:
            return None

    def _sess_title(s: ReadSession) -> str:
        try:
            return s.work.title
        except Exception:
            return f"Work {s.work_id}"

    # ── Currently reading ────────────────────────────────────────────────────
    reading_rs = [rs for rs in rs_rows if rs.status == "reading"]
    reading_rs.sort(key=lambda rs: rs.last_opened or datetime.min, reverse=True)
    currently_reading = [
        _BookProgress(
            id=_rs_display_edition_id(rs),
            title=_rs_title(rs),
            author=_rs_author(rs),
            percentage=round(work_to_pct.get(rs.work_id, 0.0), 1),
            last_opened=rs.last_opened.isoformat() if rs.last_opened else None,
        )
        for rs in reading_rs[:10]
    ]

    # ── Recently completed ────────────────────────────────────────────────────
    completed_rs = [rs for rs in rs_rows if rs.status == "completed" and rs.completed_at]
    completed_rs.sort(key=lambda rs: rs.completed_at or datetime.min, reverse=True)
    recently_completed = [
        _BookCompleted(
            id=_rs_display_edition_id(rs),
            title=_rs_title(rs),
            author=_rs_author(rs),
            completed_at=rs.completed_at.isoformat() if rs.completed_at else None,
            rating=rs.rating,
        )
        for rs in completed_rs[:10]
    ]

    # ── Recent sessions ───────────────────────────────────────────────────────
    recent_sessions = [
        _Session(
            id=s.id,
            book_id=s.work_id,
            title=_sess_title(s),
            author=_sess_author(s),
            started_at=s.started_at.isoformat(),
            finished_at=s.finished_at.isoformat() if s.finished_at else None,
            rating=s.rating,
            notes=s.notes,
        )
        for s in sessions[:20]
    ]

    # ── Monthly completions (last 12 months) ──────────────────────────────────
    months_map: dict[str, int] = {}
    for i in range(11, -1, -1):
        d = (now.replace(day=1) - timedelta(days=i * 30)).replace(day=1)
        months_map[d.strftime("%Y-%m")] = 0
    for rs in rs_rows:
        if rs.status == "completed" and rs.completed_at:
            key = rs.completed_at.strftime("%Y-%m")
            if key in months_map:
                months_map[key] += 1
    completions_by_month = [{"month": k, "count": v} for k, v in sorted(months_map.items())]

    # ── Activity heatmap (last 365 days) ──────────────────────────────────────
    cutoff = now - timedelta(days=365)
    day_counter: Counter = Counter()
    for s in sessions:
        if s.started_at and s.started_at >= cutoff:
            day_counter[s.started_at.date().isoformat()] += 1
    activity_by_day = [{"date": d, "count": c} for d, c in sorted(day_counter.items())]

    # ── Streaks ───────────────────────────────────────────────────────────────
    active_days = sorted(day_counter.keys())
    current_streak = 0
    longest_streak = 0
    if active_days:
        today_str = date.today().isoformat()
        yesterday_str = (date.today() - timedelta(days=1)).isoformat()
        run = 1
        for i in range(1, len(active_days)):
            d1 = date.fromisoformat(active_days[i])
            d2 = date.fromisoformat(active_days[i - 1])
            if (d1 - d2).days == 1:
                run += 1
                longest_streak = max(longest_streak, run)
            else:
                run = 1
        longest_streak = max(longest_streak, run)
        streak = 0
        if active_days[-1] in (today_str, yesterday_str):
            streak = 1
            for i in range(len(active_days) - 1, 0, -1):
                d1 = date.fromisoformat(active_days[i])
                d2 = date.fromisoformat(active_days[i - 1])
                if (d1 - d2).days == 1:
                    streak += 1
                else:
                    break
        current_streak = streak

    # ── Ratings ───────────────────────────────────────────────────────────────
    ratings = [rs.rating for rs in rs_rows if rs.rating]
    avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else None
    rating_counter: Counter = Counter(str(r) for r in ratings)
    rating_distribution = dict(rating_counter)

    # ── Peak reading hours (from Kobo updated_at + session started_at) ────────
    hour_counter: Counter = Counter()
    for k in kobo_states:
        if k.updated_at:
            hour_counter[k.updated_at.hour] += 1
    for s in sessions:
        if s.started_at:
            hour_counter[s.started_at.hour] += 1
    peak_hours = [{"hour": h, "count": c} for h, c in sorted(hour_counter.items())]

    # ── Day-of-week distribution ──────────────────────────────────────────────
    dow_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    dow_counter: Counter = Counter()
    for k in kobo_states:
        if k.updated_at:
            dow_counter[k.updated_at.weekday()] += 1
    for s in sessions:
        if s.started_at:
            dow_counter[s.started_at.weekday()] += 1
    day_of_week = [{"day": dow_names[d], "count": dow_counter.get(d, 0)} for d in range(7)]

    # ── Reading speed (pages per hour from Kobo data) ─────────────────────────
    reading_speed = None
    speed_samples = []
    for k in kobo_states:
        if k.time_spent_reading > 60 and k.current_page > 0:
            hours = k.time_spent_reading / 3600
            speed_samples.append(k.current_page / hours)
    if speed_samples:
        avg_speed = sum(speed_samples) / len(speed_samples)
        reading_speed = {"pages_per_hour": round(avg_speed, 1), "books_sampled": len(speed_samples)}

    # ── Time reading by month (from Kobo updated_at) ──────────────────────────
    time_month_map: dict[str, int] = {}
    for k in kobo_states:
        if k.updated_at and k.time_spent_reading > 0:
            key = k.updated_at.strftime("%Y-%m")
            time_month_map[key] = time_month_map.get(key, 0) + k.time_spent_reading
    time_by_month = [{"month": k, "seconds": v} for k, v in sorted(time_month_map.items())]

    # ── Top genres / tags ─────────────────────────────────────────────────────
    tag_counter: Counter = Counter()
    for rs in rs_rows:
        ed = work_to_edition.get(rs.work_id)
        if ed is None:
            continue
        try:
            for tag in ed.work.tags:
                tag_counter[tag.name] += 1
        except Exception:
            pass
    top_genres = [{"tag": t, "count": c} for t, c in tag_counter.most_common(10)]

    return ReadingStats(
        total_books=len(rs_rows),
        books_reading=status_counter.get("reading", 0),
        books_completed=status_counter.get("completed", 0),
        books_abandoned=status_counter.get("abandoned", 0),
        pages_read=pages_read,
        time_reading_seconds=time_reading_seconds,
        sessions_this_year=sessions_this_year,
        currently_reading=currently_reading,
        recently_completed=recently_completed,
        recent_sessions=recent_sessions,
        completions_by_month=completions_by_month,
        activity_by_day=activity_by_day,
        current_streak=current_streak,
        longest_streak=longest_streak,
        avg_rating=avg_rating,
        rating_distribution=rating_distribution,
        peak_hours=peak_hours,
        day_of_week=day_of_week,
        reading_speed=reading_speed,
        time_by_month=time_by_month,
        top_genres=top_genres,
    )
