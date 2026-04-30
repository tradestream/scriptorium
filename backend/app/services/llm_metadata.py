"""LLM-based metadata extraction — uses AI to identify book metadata from text content.

Last-resort enrichment when OPF metadata, ISBN extraction, filename parsing,
and provider lookups have all failed. Sends the first ~3000 chars of extracted
text to the configured LLM and asks it to identify title, author, publisher, etc.
"""

import json
import logging
import re
from pathlib import Path

logger = logging.getLogger("scriptorium.llm_metadata")

SYSTEM_PROMPT = """You are a librarian cataloging books. Given the first pages of a book, extract metadata.

Return ONLY a JSON object with these fields (use null for anything you can't determine):
{
  "title": "Full book title",
  "subtitle": "Subtitle if any",
  "authors": ["Author Name 1", "Author Name 2"],
  "publisher": "Publisher name",
  "published_date": "YYYY or YYYY-MM-DD",
  "isbn": "ISBN-13 if found (13 digits starting with 978 or 979)",
  "language": "English",
  "description": "1-2 sentence summary of the book's topic/content"
}

Rules:
- For authors, use "First Last" format (not "Last, First")
- Only include authors, not editors/translators (unless it's an edited volume)
- For published_date, even a year alone is useful
- For description, write an original 1-2 sentence summary, not a copy of any text
- If the text is clearly a specific edition, note the publisher of THAT edition
- Return valid JSON only, no markdown formatting"""

USER_PROMPT_TEMPLATE = """Here are the first pages of a book file named "{filename}":

---
{text}
---

Extract the book's metadata as JSON."""

# Max text to send to LLM (roughly ~1000 tokens)
MAX_TEXT_CHARS = 3000


def _extract_front_matter(text: str, max_chars: int = MAX_TEXT_CHARS) -> str:
    """Extract the most metadata-rich portion of text (front matter / copyright page)."""
    if len(text) <= max_chars:
        return text

    # Look for copyright page markers in the first 20% of the book
    search_region = text[:max(len(text) // 5, max_chars * 2)]
    copyright_markers = [
        "copyright", "isbn", "all rights reserved", "published by",
        "first published", "printing", "library of congress",
        "cataloging-in-publication", "© ", "(c) ",
    ]

    # Find the earliest copyright marker
    best_pos = max_chars
    for marker in copyright_markers:
        pos = search_region.lower().find(marker)
        if pos != -1:
            # Include context around the marker
            start = max(0, pos - 500)
            best_pos = min(best_pos, start)
            break

    # Take from the beginning up to best_pos + max_chars
    return text[:best_pos + max_chars]


async def extract_metadata_via_llm(
    text: str,
    filename: str = "",
) -> dict:
    """Send text to LLM and parse the metadata response.

    Returns dict with: title, subtitle, authors, publisher, published_date,
    isbn, language, description. All fields may be None.
    """
    from app.services.llm import get_llm_provider

    provider = get_llm_provider()
    if not provider.is_available():
        logger.warning("LLM provider not available for metadata extraction")
        return {}

    front_matter = _extract_front_matter(text)
    user_prompt = USER_PROMPT_TEMPLATE.format(
        filename=filename,
        text=front_matter,
    )

    try:
        response = await provider.generate(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            max_tokens=1024,
        )
    except Exception as exc:
        logger.warning("LLM metadata extraction failed: %s", exc)
        return {}

    # Parse JSON from response
    content = response.content.strip()
    # Strip markdown code fences if present
    content = re.sub(r'^```(?:json)?\s*', '', content)
    content = re.sub(r'\s*```$', '', content)

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        # Try to find JSON object in response
        m = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', content, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(0))
            except json.JSONDecodeError:
                logger.warning("Failed to parse LLM response as JSON: %s", content[:200])
                return {}
        else:
            logger.warning("No JSON found in LLM response: %s", content[:200])
            return {}

    # Normalize
    result = {
        "title": data.get("title"),
        "subtitle": data.get("subtitle"),
        "authors": data.get("authors") or [],
        "publisher": data.get("publisher"),
        "published_date": data.get("published_date"),
        "isbn": None,
        "language": data.get("language"),
        "description": data.get("description"),
    }

    # Validate ISBN if provided
    raw_isbn = data.get("isbn")
    if raw_isbn:
        clean = re.sub(r'[\s-]', '', str(raw_isbn))
        if re.match(r'^97[89]\d{10}$', clean):
            result["isbn"] = clean
        elif re.match(r'^\d{9}[\dXx]$', clean):
            result["isbn"] = clean

    # Ensure authors is a list
    if isinstance(result["authors"], str):
        result["authors"] = [result["authors"]]

    return result


async def extract_llm_metadata_for_edition(edition_id: int) -> dict:
    """Extract metadata via LLM for a single edition.

    Only fills in fields that are currently empty.
    Returns dict of fields that were found and applied.
    """
    from sqlalchemy import select
    from sqlalchemy.orm import joinedload

    from app.config import resolve_path
    from app.database import get_session_factory
    from app.models.book import Author
    from app.models.edition import Edition
    from app.models.work import Work
    from app.services.text_extraction import (
        _extract_epub_plain,
        _extract_pdf_text,
        optimize_for_llm,
    )

    factory = get_session_factory()

    # Phase 1: load edition and check what's missing
    async with factory() as db:
        result = await db.execute(
            select(Edition)
            .where(Edition.id == edition_id)
            .options(
                joinedload(Edition.files),
                joinedload(Edition.work).options(joinedload(Work.authors)),
            )
        )
        edition = result.unique().scalar_one_or_none()
        if not edition or not edition.files:
            return {}

        work = edition.work
        missing_title = not work or not work.title or work.title.startswith("0") or len(work.title) <= 3
        missing_authors = not work or not work.authors
        missing_description = not work or not work.description
        missing_publisher = not edition.publisher
        missing_isbn = not edition.isbn

        # Skip if nothing is missing
        if not any([missing_title, missing_authors, missing_description, missing_publisher, missing_isbn]):
            return {}

        # Find extractable file
        priority = {"epub": 0, "pdf": 1}
        eligible = [f for f in edition.files if f.format.lower() in priority]
        if not eligible:
            return {}
        eligible.sort(key=lambda f: priority.get(f.format.lower(), 99))

        fpath = Path(resolve_path(eligible[0].file_path))
        fmt = eligible[0].format.lower()
        filename = eligible[0].filename

        if not fpath.exists():
            return {}

    # Phase 2: extract text (limited to front matter)
    try:
        if fmt == "epub":
            text = await _extract_epub_plain(fpath)
        elif fmt == "pdf":
            text = await _extract_pdf_text(fpath)
        else:
            return {}

        if not text or len(text.strip()) < 100:
            return {}

        # Only need front matter for metadata
        text = text[:MAX_TEXT_CHARS * 2]
        text = optimize_for_llm(text)
    except Exception as exc:
        logger.debug("Text extraction failed for edition %d: %s", edition_id, exc)
        return {}

    # Phase 3: LLM extraction
    meta = await extract_metadata_via_llm(text, filename)
    if not meta:
        return {}

    # Phase 4: apply to DB (only fill empty fields)
    found = {}
    async with factory() as db:
        result = await db.execute(
            select(Edition)
            .where(Edition.id == edition_id)
            .options(joinedload(Edition.work).options(joinedload(Work.authors)))
        )
        edition = result.unique().scalar_one_or_none()
        if not edition:
            return {}

        work = edition.work

        if meta.get("title") and missing_title and work:
            work.title = meta["title"]
            if meta.get("subtitle"):
                work.subtitle = meta["subtitle"]
            found["title"] = True

        if meta.get("authors") and missing_authors and work:
            for aname in meta["authors"]:
                if not aname or len(aname) < 2:
                    continue
                existing = await db.execute(select(Author).where(Author.name == aname))
                author = existing.scalar_one_or_none()
                if not author:
                    author = Author(name=aname)
                    db.add(author)
                    await db.flush()
                if author not in work.authors:
                    work.authors.append(author)
            found["authors"] = True

        if meta.get("description") and missing_description and work:
            work.description = meta["description"]
            found["description"] = True

        if meta.get("publisher") and missing_publisher:
            edition.publisher = meta["publisher"]
            found["publisher"] = True

        if meta.get("isbn") and missing_isbn:
            from app.utils.isbn import normalize
            isbn13, isbn10 = normalize(meta["isbn"])
            if isbn13:
                edition.isbn = isbn13
                edition.isbn_10 = isbn10
                found["isbn"] = True

        if meta.get("language") and not edition.language:
            edition.language = meta["language"]
            found["language"] = True

        if meta.get("published_date") and not edition.published_date:
            edition.published_date = meta["published_date"][:10]
            found["date"] = True

        await db.commit()

    return found
