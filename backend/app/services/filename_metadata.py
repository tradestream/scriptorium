"""Filename metadata extraction — parses title/author from file paths.

Handles common naming patterns:
- "Title - Author.epub"
- "Title - Author (Year).epub"
- "Author/Title.epub" (author from parent folder)
- Calibre-style "Author/Title (ID)/Title - Author.epub"

Adapted from booklore-tools/filename-metadata/extract_metadata.py.
"""

import re
from pathlib import Path
from typing import Optional


def _clean_text(text: str) -> str:
    """Clean up extracted text."""
    if not text:
        return ""
    text = re.sub(r'[_\-\.]+$', '', text)
    text = re.sub(r'^[_\-\.]+', '', text)
    # Calibre uses _ to replace : in filenames
    text = re.sub(r'(\w)_\s', r'\1: ', text)
    text = text.replace('_', ' ')
    return re.sub(r'\s+', ' ', text).strip()


def _normalize_author(author: str) -> str:
    """Normalize author name to 'Lastname, Firstname' format."""
    if not author:
        return ""
    author = _clean_text(author)

    skip = [
        r'^unknown$', r'^various$', r'^anonymous$', r'^n/?a$',
        r'^www\.', r'^http', r'\.com$', r'\.org$',
        r'^calibre$', r'^ebook', r'^\d+$',
    ]
    for pat in skip:
        if re.search(pat, author.lower()):
            return ""

    # Already "Lastname, Firstname"
    if ',' in author:
        parts = [p.strip() for p in author.split(',', 1)]
        if len(parts) == 2 and parts[0] and parts[1]:
            return f"{parts[0]}, {parts[1]}"

    words = author.split()
    if len(words) == 2:
        return f"{words[1]}, {words[0]}"
    elif len(words) == 3:
        if words[2].lower() in ('jr', 'jr.', 'sr', 'sr.', 'ii', 'iii', 'iv'):
            return f"{words[1]} {words[2]}, {words[0]}"
        else:
            return f"{words[2]}, {words[0]} {words[1]}"
    elif len(words) == 1:
        return words[0]
    return author


def _extract_year(text: str) -> Optional[int]:
    """Extract publication year from text."""
    m = re.search(r'\((\d{4})\)\s*$', text)
    if m:
        year = int(m.group(1))
        if 1900 <= year <= 2035:
            return year
    m = re.search(r'[_\-\s](\d{4})$', text)
    if m:
        year = int(m.group(1))
        if 1900 <= year <= 2035:
            return year
    return None


def extract_from_filename(filename: str, folder_path: str = "") -> dict:
    """Extract metadata from filename and folder structure.

    Returns dict with title, author, year, confidence, source.
    """
    result = {"title": None, "author": None, "year": None, "confidence": "low", "source": ""}

    base = Path(filename).stem

    # Extract year
    result["year"] = _extract_year(base)
    if result["year"]:
        base = re.sub(r'\s*\(\d{4}\)\s*$', '', base)
        base = re.sub(r'[_\-\s]\d{4}$', '', base)

    # Get folder name as potential author
    folder_author = ""
    if folder_path:
        parts = Path(folder_path).parts
        if parts:
            potential = parts[-1] if len(parts) >= 1 else ""
            # Skip generic folder names
            if potential.lower() not in ('books', 'ebooks', 'epub', 'pdf', 'downloads', 'library', 'ingest', ''):
                # Skip Calibre numeric IDs like "Title (123)"
                if not re.match(r'.+\s*\(\d+\)$', potential):
                    folder_author = potential

    # Pattern 1: "Title - Author"
    m = re.match(r'^(.+?)\s+[-\u2013\u2014]\s+(.+)$', base)
    if m:
        potential_title = _clean_text(m.group(1))
        potential_author = m.group(2)

        # Handle "Title - Subtitle - Author"
        if ' - ' in potential_author or ' \u2013 ' in potential_author:
            parts = re.split(r'\s+[-\u2013\u2014]\s+', potential_author)
            potential_author = parts[-1]

        potential_author = _clean_text(potential_author)

        if re.search(r'^\d{4}$', potential_author):
            potential_author = ""
        if re.search(r'^(Edition|Vol|Volume|Part|Book)\s*\d', potential_author, re.I):
            potential_author = ""

        if potential_title and potential_author:
            result["title"] = potential_title
            result["author"] = _normalize_author(potential_author)
            result["confidence"] = "high"
            result["source"] = "filename: Title - Author"
            return result
        elif potential_title and folder_author:
            result["title"] = potential_title
            result["author"] = _normalize_author(folder_author)
            result["confidence"] = "high"
            result["source"] = "title from filename, author from folder"
            return result
        elif potential_title:
            result["title"] = potential_title
            result["confidence"] = "medium"
            result["source"] = "filename: title only"
            return result

    # Pattern 2: Title in filename, author in folder
    if folder_author:
        result["title"] = _clean_text(base)
        result["author"] = _normalize_author(folder_author)
        result["confidence"] = "medium"
        result["source"] = "title from filename, author from folder"
        return result

    # Pattern 3: Just the title
    result["title"] = _clean_text(base)
    result["confidence"] = "low"
    result["source"] = "filename only"
    return result


async def extract_and_apply(edition_id: int, min_confidence: str = "medium") -> dict:
    """Extract metadata from an edition's filename and apply if missing.

    Only fills in fields that are currently empty/generic.
    Returns dict with what was found and applied.
    """
    confidence_order = {"low": 0, "medium": 1, "high": 2}
    min_conf = confidence_order.get(min_confidence, 1)

    from sqlalchemy import select
    from sqlalchemy.orm import joinedload
    from app.database import get_session_factory
    from app.models.edition import Edition, EditionFile
    from app.models.work import Work
    from app.models.book import Author

    factory = get_session_factory()
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
            return {"status": "no_files"}

        work = edition.work
        best_file = edition.files[0]
        file_path = best_file.file_path
        filename = best_file.filename

        # Get folder path relative to filename
        folder = str(Path(file_path).parent) if file_path else ""

        extracted = extract_from_filename(filename, folder)

        if confidence_order.get(extracted["confidence"], 0) < min_conf:
            return {"status": "low_confidence", **extracted}

        # Check what's missing
        title_missing = not work.title or work.title == Path(filename).stem or work.title.lower() in ('unknown', 'untitled')
        authors_missing = not work.authors or all(a.name.lower() in ('unknown', 'unknown author', 'various', '') for a in work.authors)

        applied = {}
        if title_missing and extracted["title"]:
            work.title = extracted["title"]
            applied["title"] = extracted["title"]

        if authors_missing and extracted["author"]:
            # Get or create author
            from sqlalchemy import select as _sel
            r = await db.execute(_sel(Author).where(Author.name == extracted["author"]))
            author = r.scalar_one_or_none()
            if not author:
                author = Author(name=extracted["author"])
                db.add(author)
                await db.flush()
            work.authors = [author]
            applied["author"] = extracted["author"]

        if extracted["year"] and not edition.published_date:
            from datetime import datetime
            edition.published_date = datetime(extracted["year"], 1, 1)
            applied["year"] = extracted["year"]

        if applied:
            await db.commit()

        return {"status": "applied" if applied else "nothing_missing", "extracted": extracted, "applied": applied}
