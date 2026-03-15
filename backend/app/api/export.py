"""Export endpoints — annotated HTML edition, per-book."""

import json
from collections import defaultdict
from html import escape

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api.auth import get_current_user
from app.database import get_db
from app.models import Book, User
from app.models.annotation import Annotation
from app.models.marginalium import Marginalium

router = APIRouter(prefix="/export", tags=["export"])


# ── Kind metadata ──────────────────────────────────────────────────────────────

KIND_META: dict[str, tuple[str, str]] = {
    "observation": ("Observation", "#64748b"),
    "insight":     ("Insight",     "#d97706"),
    "question":    ("Question",    "#2563eb"),
    "theme":       ("Theme",       "#16a34a"),
    "symbol":      ("Symbol",      "#9333ea"),
    "character":   ("Character",   "#ea580c"),
    "parallel":    ("Parallel",    "#0891b2"),
    "structure":   ("Structure",   "#e11d48"),
    "context":     ("Context",     "#0d9488"),
    "esoteric":    ("Esoteric",    "#7c3aed"),
}

ANNOT_TYPE_META: dict[str, tuple[str, str]] = {
    "highlight": ("Highlight", "#ca8a04"),
    "note":      ("Note",      "#0369a1"),
    "bookmark":  ("Bookmark",  "#15803d"),
}

# Inline CSS for the exported document
_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: Georgia, 'Times New Roman', serif;
    font-size: 15px;
    line-height: 1.7;
    color: #1a1a1a;
    max-width: 800px;
    margin: 0 auto;
    padding: 2rem 1.5rem 4rem;
    background: #fafaf9;
}
header {
    border-bottom: 2px solid #1a1a1a;
    padding-bottom: 1.5rem;
    margin-bottom: 2rem;
}
header h1 { font-size: 2rem; font-weight: 700; line-height: 1.2; }
header .author { font-size: 1rem; color: #555; margin-top: 0.4rem; font-style: italic; }
header .meta { font-size: 0.8rem; color: #888; margin-top: 0.8rem; }
nav {
    background: #f5f5f4;
    border: 1px solid #d6d3d1;
    border-radius: 6px;
    padding: 1rem 1.5rem;
    margin-bottom: 2.5rem;
}
nav h2 { font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.08em; color: #78716c; margin-bottom: 0.75rem; }
nav ol { padding-left: 1.25rem; }
nav li { font-size: 0.875rem; margin-bottom: 0.25rem; }
nav a { color: #44403c; text-decoration: none; }
nav a:hover { text-decoration: underline; }
nav .count { color: #a8a29e; font-size: 0.75rem; }
section.chapter { margin-bottom: 3rem; }
section.chapter h2 {
    font-size: 1.1rem;
    font-weight: 600;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid #d6d3d1;
    margin-bottom: 1.25rem;
    color: #292524;
}
.note-card {
    border: 1px solid #e7e5e4;
    border-left: 4px solid #a8a29e;
    border-radius: 4px;
    padding: 0.75rem 1rem;
    margin-bottom: 0.75rem;
    background: #fff;
}
.note-card .card-header {
    display: flex;
    align-items: flex-start;
    gap: 0.5rem;
    margin-bottom: 0.5rem;
    flex-wrap: wrap;
}
.pill {
    display: inline-block;
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    padding: 0.1rem 0.5rem;
    border-radius: 9999px;
    color: #fff;
}
.note-card .location {
    font-size: 0.75rem;
    color: #78716c;
    margin-left: auto;
}
.note-card .content {
    font-size: 0.9rem;
    line-height: 1.65;
    color: #292524;
    margin-bottom: 0.35rem;
}
.note-card .tags {
    display: flex;
    flex-wrap: wrap;
    gap: 0.3rem;
    margin-top: 0.35rem;
}
.tag {
    font-size: 0.7rem;
    background: #f5f5f4;
    color: #78716c;
    border: 1px solid #e7e5e4;
    border-radius: 3px;
    padding: 0.05rem 0.35rem;
}
.attribution {
    font-size: 0.78rem;
    font-style: italic;
    color: #78716c;
    margin-top: 0.35rem;
}
.related {
    font-size: 0.75rem;
    color: #a8a29e;
    margin-top: 0.25rem;
}
footer {
    margin-top: 3rem;
    padding-top: 1rem;
    border-top: 1px solid #d6d3d1;
    font-size: 0.75rem;
    color: #a8a29e;
    text-align: center;
}
@media print {
    body { background: #fff; padding: 0; }
    .note-card { break-inside: avoid; }
}
"""


def _pill(label: str, color: str) -> str:
    return f'<span class="pill" style="background:{color}">{escape(label)}</span>'


def _render_note_card(
    content: str,
    pill_html: str,
    border_color: str,
    location: str | None = None,
    tags: list[str] | None = None,
    related_refs: list[str] | None = None,
    commentator: str | None = None,
    source: str | None = None,
) -> str:
    parts = [f'<div class="note-card" style="border-left-color:{border_color}">']
    parts.append('<div class="card-header">')
    parts.append(pill_html)
    if location:
        parts.append(f'<span class="location">{escape(location)}</span>')
    parts.append('</div>')
    parts.append(f'<p class="content">{escape(content)}</p>')
    if tags:
        tag_html = "".join(f'<span class="tag">{escape(t)}</span>' for t in tags)
        parts.append(f'<div class="tags">{tag_html}</div>')
    if related_refs:
        parts.append(f'<p class="related">→ {escape(", ".join(related_refs))}</p>')
    if commentator:
        attr = escape(commentator)
        if source:
            attr += f", {escape(source)}"
        parts.append(f'<p class="attribution">— {attr}</p>')
    parts.append('</div>')
    return "".join(parts)


def _parse_json_list(v: str | None) -> list[str]:
    if not v:
        return []
    try:
        parsed = json.loads(v)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return [s.strip() for s in v.split(",") if s.strip()]


@router.get("/books/{book_id}/annotated", response_class=HTMLResponse)
async def export_annotated_html(
    book_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate a self-contained annotated HTML edition for a book.

    Groups all marginalia + annotations by chapter, with color-coded kind
    pills, attribution, tags, and related references. Suitable for printing
    or archiving as a personal scholarly edition.
    """
    # Load book
    bk_result = await db.execute(
        select(Book).options(joinedload(Book.authors)).where(Book.id == book_id)
    )
    book = bk_result.unique().scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")

    author_name = book.authors[0].name if book.authors else None

    # Load marginalia
    mar_result = await db.execute(
        select(Marginalium).where(
            Marginalium.user_id == current_user.id,
            Marginalium.book_id == book_id,
        ).order_by(Marginalium.chapter, Marginalium.created_at)
    )
    marginalia = mar_result.scalars().all()

    # Load annotations
    ann_result = await db.execute(
        select(Annotation).where(
            Annotation.user_id == current_user.id,
            Annotation.book_id == book_id,
        ).order_by(Annotation.chapter, Annotation.created_at)
    )
    annotations = ann_result.scalars().all()

    # Group into chapters
    chapters: dict[str, list[str]] = defaultdict(list)

    for m in marginalia:
        ch = m.chapter or "Uncategorized"
        label, color = KIND_META.get(m.kind, (m.kind.capitalize(), "#78716c"))
        card = _render_note_card(
            content=m.content,
            pill_html=_pill(label, color),
            border_color=color,
            location=m.location,
            tags=_parse_json_list(m.tags),
            related_refs=_parse_json_list(m.related_refs),
            commentator=m.commentator,
            source=m.source,
        )
        chapters[ch].append(card)

    for a in annotations:
        if not a.content:
            continue
        ch = a.chapter or "Uncategorized"
        a_type = (a.type or "note").lower()
        label, color = ANNOT_TYPE_META.get(a_type, (a_type.capitalize(), "#78716c"))
        loc = a.location
        card = _render_note_card(
            content=a.content,
            pill_html=_pill(label, color),
            border_color=color,
            location=loc,
            tags=_parse_json_list(a.tags),
            related_refs=_parse_json_list(a.related_refs),
            commentator=a.commentator,
            source=a.source,
        )
        chapters[ch].append(card)

    if not chapters:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No annotations or marginalia found for this book.",
        )

    # Sort chapters: put named chapters first in order, Uncategorized last
    chapter_keys = sorted(
        chapters.keys(),
        key=lambda k: (k == "Uncategorized", k),
    )

    total_notes = sum(len(v) for v in chapters.values())
    from datetime import datetime
    generated = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    # Build HTML
    title_esc = escape(book.title)
    author_esc = escape(author_name) if author_name else ""

    # TOC
    toc_items = []
    for ch in chapter_keys:
        ch_id = f"ch-{escape(ch).replace(' ', '-').lower()}"
        toc_items.append(
            f'<li><a href="#{ch_id}">{escape(ch)}</a> '
            f'<span class="count">({len(chapters[ch])})</span></li>'
        )

    # Chapters
    chapter_sections = []
    for ch in chapter_keys:
        ch_id = f"ch-{escape(ch).replace(' ', '-').lower()}"
        cards_html = "\n".join(chapters[ch])
        chapter_sections.append(
            f'<section class="chapter" id="{ch_id}">'
            f'<h2>{escape(ch)}</h2>'
            f'{cards_html}'
            f'</section>'
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title_esc} — Annotated Edition</title>
<style>{_CSS}</style>
</head>
<body>
<header>
  <h1>{title_esc}</h1>
  {"<p class='author'>" + author_esc + "</p>" if author_esc else ""}
  <p class="meta">Annotated edition &mdash; {total_notes} note{"s" if total_notes != 1 else ""} &mdash; generated {generated}</p>
</header>
<nav>
  <h2>Contents</h2>
  <ol>{"".join(toc_items)}</ol>
</nav>
{"".join(chapter_sections)}
<footer>Generated by Scriptorium</footer>
</body>
</html>"""

    safe_title = "".join(c if c.isalnum() or c in "- " else "_" for c in book.title)[:60].strip()
    filename = f"{safe_title}_annotated.html"

    return HTMLResponse(
        content=html,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
