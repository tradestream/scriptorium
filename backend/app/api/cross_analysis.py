"""Cross-book esoteric analysis — put books and their analyses in conversation."""

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api.auth import get_current_user
from app.database import get_db
from app.models import Book, User
from app.models.analysis import ComputationalAnalysis, BookAnalysis
from app.models.work import Work

router = APIRouter(prefix="/cross-analysis", tags=["cross-analysis"])


# ── Corpus-wide metrics ──────────────────────────────────────────────────────

@router.get("/dashboard")
async def esoteric_dashboard(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Aggregate esoteric analysis stats across the corpus."""
    # Count books with analyses
    total_enabled = await db.scalar(
        select(func.count(Work.id)).where(Work.esoteric_enabled == True)
    )
    total_computational = await db.scalar(
        select(func.count(func.distinct(ComputationalAnalysis.book_id)))
        .where(ComputationalAnalysis.status == "completed")
    )
    total_llm = await db.scalar(
        select(func.count(func.distinct(BookAnalysis.book_id)))
        .where(BookAnalysis.status == "completed")
    )

    return {
        "total_esoteric_enabled": total_enabled,
        "total_with_computational": total_computational,
        "total_with_llm": total_llm,
    }


# ── Cross-book comparison ────────────────────────────────────────────────────

@router.get("/scores")
async def compare_esoteric_scores(
    metric: str = "audience_differentiation",
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Rank books by a specific computational esoteric metric.

    Available metrics: audience_differentiation, hedging_language,
    self_reference, structural_obscurity, conditional_language,
    exoteric_esoteric_ratio.
    """
    results = await db.execute(
        select(ComputationalAnalysis)
        .where(
            ComputationalAnalysis.analysis_type == "full",
            ComputationalAnalysis.status == "completed",
        )
    )
    analyses = results.scalars().all()

    scored = []
    for a in analyses:
        try:
            data = json.loads(a.results_json)
        except Exception:
            continue

        tool_data = data.get(metric, {})
        if not tool_data or tool_data.get("error"):
            continue

        # Extract score based on metric type
        score = None
        if metric == "audience_differentiation":
            score = tool_data.get("differentiation_score", 0)
        elif metric == "hedging_language":
            score = tool_data.get("hedge_density", 0)
        elif metric == "self_reference":
            score = tool_data.get("meta_esoteric_score", 0)
        elif metric == "conditional_language":
            score = tool_data.get("density", 0)
        elif metric == "structural_obscurity":
            score = 1.0 - tool_data.get("plan_regularity_score", 1.0)  # Invert: higher = more obscure
        elif metric == "exoteric_esoteric_ratio":
            total_p = tool_data.get("overall_pious", 0)
            total_s = tool_data.get("overall_subversive", 0)
            score = total_s / (total_p + total_s) if (total_p + total_s) > 0 else 0

        if score is not None and score > 0:
            scored.append({"book_id": a.book_id, "score": round(score, 4)})

    scored.sort(key=lambda x: x["score"], reverse=True)
    scored = scored[:limit]

    # Enrich with book titles
    if scored:
        book_ids = [s["book_id"] for s in scored]
        book_result = await db.execute(
            select(Book.id, Work.title)
            .join(Book.work)
            .where(Book.id.in_(book_ids))
        )
        title_map = {bid: title for bid, title in book_result.all()}
        for s in scored:
            s["title"] = title_map.get(s["book_id"], "Unknown")

    return {"metric": metric, "results": scored}


# ── Cross-book LLM conversation ──────────────────────────────────────────────

class CrossAnalysisRequest(BaseModel):
    book_ids: list[int]
    prompt: Optional[str] = None


@router.post("/conversation")
async def cross_book_conversation(
    request: CrossAnalysisRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send multiple books' analyses to the LLM for cross-book conversation.

    Gathers all computational and LLM analyses for the specified books,
    then asks the LLM to find connections, contradictions, and patterns
    across them.
    """
    from app.services.llm import get_llm_provider

    provider = get_llm_provider()
    if not provider.is_available():
        raise HTTPException(status_code=503, detail="LLM provider not configured")

    # Gather analyses for all books
    book_summaries = []
    for book_id in request.book_ids[:10]:  # Cap at 10 books
        # Get book info
        book_result = await db.execute(
            select(Book).where(Book.id == book_id).options(
                joinedload(Book.work).options(joinedload(Work.authors))
            )
        )
        book = book_result.unique().scalar_one_or_none()
        if not book:
            continue

        title = book.work.title if book.work else "Unknown"
        authors = ", ".join(a.name for a in book.authors) if book.authors else "Unknown"

        # Get computational summary
        comp_result = await db.execute(
            select(ComputationalAnalysis)
            .where(ComputationalAnalysis.book_id == book_id, ComputationalAnalysis.status == "completed")
            .order_by(ComputationalAnalysis.created_at.desc())
            .limit(1)
        )
        comp = comp_result.scalar_one_or_none()

        comp_summary = ""
        if comp:
            try:
                data = json.loads(comp.results_json)
                parts = []
                aud = data.get("audience_differentiation", {})
                if aud and not aud.get("error"):
                    parts.append(f"Audience differentiation score: {aud.get('differentiation_score', 0)}")
                hedge = data.get("hedging_language", {})
                if hedge and not hedge.get("error"):
                    parts.append(f"Hedging density: {hedge.get('hedge_density', 0)}/1000 words")
                selfref = data.get("self_reference", {})
                if selfref and not selfref.get("error"):
                    parts.append(f"Meta-esoteric score: {selfref.get('meta_esoteric_score', 0)}")
                fl = data.get("first_last_words", {})
                if fl and not fl.get("error"):
                    oc = fl.get("opening_closing_words", {})
                    parts.append(f"First word: {oc.get('first_word', '?')}, Last word: {oc.get('last_word', '?')}")
                ratio = data.get("exoteric_esoteric_ratio", {})
                if ratio and not ratio.get("error"):
                    parts.append(f"Pious: {ratio.get('overall_pious', 0)}, Subversive: {ratio.get('overall_subversive', 0)}")
                comp_summary = "; ".join(parts)
            except Exception:
                pass

        # Get LLM analysis summaries (first 500 chars of each)
        llm_result = await db.execute(
            select(BookAnalysis)
            .where(BookAnalysis.book_id == book_id, BookAnalysis.status == "completed")
            .order_by(BookAnalysis.created_at.desc())
            .limit(3)
        )
        llm_summaries = []
        for a in llm_result.scalars().all():
            if a.content:
                llm_summaries.append(f"[{a.title}]: {a.content[:500]}")

        book_summaries.append({
            "title": title,
            "author": authors,
            "computational": comp_summary,
            "llm_analyses": llm_summaries,
        })

    if not book_summaries:
        raise HTTPException(status_code=404, detail="No analysed books found")

    # Build the cross-analysis prompt
    books_text = ""
    for bs in book_summaries:
        books_text += f"\n\n--- {bs['title']} by {bs['author']} ---\n"
        if bs["computational"]:
            books_text += f"Computational: {bs['computational']}\n"
        for llm in bs["llm_analyses"]:
            books_text += f"{llm}\n"

    custom_prompt = request.prompt or (
        "Compare and contrast the esoteric techniques used across these books. "
        "What patterns connect them? Where do they diverge? "
        "What does one book's esoteric strategy reveal about another's? "
        "Can insights from reading one book esoterically illuminate hidden meanings in the others?"
    )

    system_prompt = (
        "You are an expert in Straussian hermeneutics performing cross-book esoteric analysis. "
        "You have been given the esoteric analysis results for multiple books. Your task is to "
        "put these books 'in conversation' — finding how one author's esoteric strategy illuminates "
        "another's, how the same techniques appear across different works, and what the pattern of "
        "esotericism across a corpus reveals about the tradition of philosophical writing."
    )

    user_prompt = f"{custom_prompt}\n\nBooks and their analyses:{books_text}"

    response = await provider.generate(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=4096,
    )

    return {
        "books": [{"id": bid, "title": bs["title"]} for bid, bs in zip(request.book_ids, book_summaries)],
        "analysis": response.content,
        "model": response.model,
        "tokens": response.total_tokens,
    }
