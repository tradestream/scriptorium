"""Reading level computation — Flesch-Kincaid grade level from book text.

Computes readability scores from cached markdown or live text extraction.
Flesch-Kincaid Grade Level formula:
  0.39 * (total_words / total_sentences) + 11.8 * (total_syllables / total_words) - 15.59
"""

import logging
import re

logger = logging.getLogger("scriptorium.reading_level")


def _count_syllables(word: str) -> int:
    """Estimate syllable count for an English word."""
    word = word.lower().strip()
    if not word:
        return 0
    if len(word) <= 3:
        return 1

    # Remove trailing silent e
    if word.endswith('e') and not word.endswith('le'):
        word = word[:-1]

    # Count vowel groups
    count = len(re.findall(r'[aeiouy]+', word))
    return max(count, 1)


def flesch_kincaid_grade(text: str) -> float | None:
    """Compute Flesch-Kincaid Grade Level from text.

    Returns a float grade level (e.g. 8.2 = 8th grade, 2nd month).
    Returns None if text is too short.
    """
    # Clean markdown syntax
    text = re.sub(r'#+ ', '', text)
    text = re.sub(r'\*+', '', text)
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    text = re.sub(r'---+', '', text)

    # Split into sentences
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]

    if len(sentences) < 3:
        return None

    # Split into words
    words = re.findall(r"[a-zA-Z']+", text)
    if len(words) < 100:
        return None

    total_words = len(words)
    total_sentences = len(sentences)
    total_syllables = sum(_count_syllables(w) for w in words)

    grade = (
        0.39 * (total_words / total_sentences)
        + 11.8 * (total_syllables / total_words)
        - 15.59
    )

    return round(max(grade, 0), 1)


async def compute_reading_level(work_id: int) -> dict:
    """Compute Flesch-Kincaid grade level for a work.

    Uses cached markdown if available, otherwise extracts from primary edition file.
    Updates the work's flesch_kincaid_grade field.
    Returns dict with grade level or error.
    """
    from sqlalchemy import select
    from sqlalchemy.orm import joinedload

    from app.database import get_session_factory
    from app.models.work import Work
    from app.services.markdown import has_cached_markdown, markdown_path_for

    factory = get_session_factory()
    async with factory() as db:
        result = await db.execute(
            select(Work).where(Work.id == work_id).options(joinedload(Work.editions))
        )
        work = result.unique().scalar_one_or_none()
        if not work:
            return {"status": "not_found"}

        # Find an edition with cached markdown or a text file
        text = None
        for edition in work.editions:
            if has_cached_markdown(edition.uuid):
                text = markdown_path_for(edition.uuid).read_text(encoding="utf-8")
                break

        if not text:
            # Try live extraction from primary edition
            for edition in work.editions:
                if edition.files:
                    try:
                        from app.services.text_extraction import extract_text_from_book
                        text = await extract_text_from_book(edition, db, max_chars=500_000)
                        break
                    except Exception:
                        continue

        if not text or len(text) < 500:
            return {"status": "insufficient_text"}

        grade = flesch_kincaid_grade(text)
        if grade is None:
            return {"status": "insufficient_text"}

        work.flesch_kincaid_grade = grade
        await db.commit()

        return {"status": "computed", "flesch_kincaid_grade": grade}
