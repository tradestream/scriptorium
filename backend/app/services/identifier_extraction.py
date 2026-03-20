"""Identifier extraction service — scans book file content for ISBN and DOI.

Goes beyond OPF metadata by scanning actual page content (copyright pages,
front/back matter) using regex patterns with checksum validation.

Adapted from booklore-tools/isbn/isbn_extractor.py with DOI extraction added.
"""

import logging
import re
import zipfile
from pathlib import Path
from typing import Optional

from app.utils.isbn import clean as isbn_clean, is_isbn10, is_isbn13, validate_isbn10_checksum, validate_isbn13_checksum, isbn10_to_isbn13, isbn13_to_isbn10

logger = logging.getLogger("scriptorium.identifiers")


# ── ISBN patterns ────────────────────────────────────────────────────────────

# Repeating-digit ISBNs to reject
_INVALID_ISBNS = {d * 10 for d in "0123456789"} | {d * 13 for d in "0123456789"}

ISBN_PATTERNS = [
    # ISBN-13 with explicit label
    re.compile(
        r'ISBN[-\u2013:]?\s*(?:13[-\u2013:]?\s*)?'
        r'(97[89][-\u2013.\s]?(?:\d[-\u2013.\s]?){9}\d)',
        re.IGNORECASE,
    ),
    # ISBN-10 with explicit label
    re.compile(
        r'ISBN[-\u2013:]?\s*(?:10[-\u2013:]?\s*)?'
        r'(\d[-\u2013.\s]?(?:\d[-\u2013.\s]?){8}[\dXx])',
        re.IGNORECASE,
    ),
    # Standalone ISBN-13 (978/979 prefix)
    re.compile(r'\b(97[89][-\u2013.\s]?\d[-\u2013.\s]?\d{2,5}[-\u2013.\s]?\d{2,7}[-\u2013.\s]?\d)\b'),
    # Standalone ISBN-10
    re.compile(r'\b(\d[-\u2013.\s]?\d{2,5}[-\u2013.\s]?\d{2,7}[-\u2013.\s]?[\dXx])\b'),
    # EAN/barcode style (no separators)
    re.compile(r'\b(97[89]\d{10})\b'),
    re.compile(r'\b(\d{9}[\dXx])\b'),
]

# ── DOI patterns ─────────────────────────────────────────────────────────────

DOI_PATTERNS = [
    # Explicit DOI label
    re.compile(r'(?:DOI|doi)[:\s]+\s*(10\.\d{4,9}/[^\s,;>\]\"\']+)', re.IGNORECASE),
    # URL form
    re.compile(r'(?:https?://)?(?:dx\.)?doi\.org/(10\.\d{4,9}/[^\s,;>\]\"\']+)', re.IGNORECASE),
    # Standalone DOI (more conservative)
    re.compile(r'\b(10\.\d{4,9}/(?:(?!["\'<>\s])\S)+)\b'),
]

# ── HTML cleanup ─────────────────────────────────────────────────────────────

_HTML_STRIP = [
    re.compile(r'<style[^>]*>.*?</style>', re.DOTALL | re.IGNORECASE),
    re.compile(r'<script[^>]*>.*?</script>', re.DOTALL | re.IGNORECASE),
    re.compile(r'<!--.*?-->', re.DOTALL),
]
_HTML_TAG = re.compile(r'<[^>]+>')


def _clean_html(html: str) -> str:
    for pat in _HTML_STRIP:
        html = pat.sub('', html)
    return _HTML_TAG.sub(' ', html)


# ── ISBN helpers ─────────────────────────────────────────────────────────────

def _validate_isbn(raw: str) -> tuple[str | None, str | None]:
    """Validate and return (isbn_13, isbn_10) or (None, None)."""
    v = isbn_clean(raw)
    if v in _INVALID_ISBNS:
        return None, None

    if len(v) == 13 and v.isdigit():
        if validate_isbn13_checksum(v):
            isbn10 = isbn13_to_isbn10(v)
            return v, isbn10
    elif len(v) == 10 and v[:9].isdigit() and (v[9].isdigit() or v[9] in "xX"):
        if validate_isbn10_checksum(v):
            isbn13 = isbn10_to_isbn13(v)
            return isbn13, v

    return None, None


def _find_isbn_in_text(text: str) -> tuple[str | None, str | None]:
    """Find first valid ISBN in text. Returns (isbn_13, isbn_10)."""
    candidates = []
    for pat in ISBN_PATTERNS:
        for m in pat.finditer(text):
            candidates.append((isbn_clean(m.group(1)), m.start()))

    candidates.sort(key=lambda x: x[1])
    for raw, _ in candidates:
        isbn13, isbn10 = _validate_isbn(raw)
        if isbn13:
            return isbn13, isbn10
    return None, None


# ── DOI helpers ──────────────────────────────────────────────────────────────

def _clean_doi(raw: str) -> str:
    """Strip trailing punctuation that got captured by regex."""
    return raw.rstrip('.,;:)]\'"')


def _find_doi_in_text(text: str) -> str | None:
    """Find first DOI in text."""
    for pat in DOI_PATTERNS:
        m = pat.search(text)
        if m:
            return _clean_doi(m.group(1))
    return None


# ── EPUB extraction ──────────────────────────────────────────────────────────

def _get_epub_spine_files(zf: zipfile.ZipFile) -> list[str]:
    """Get content file paths from EPUB in spine order."""
    opf_path = None
    try:
        container = zf.read('META-INF/container.xml').decode('utf-8')
        m = re.search(r'rootfile[^>]+full-path="([^"]+)"', container)
        if m:
            opf_path = m.group(1)
    except Exception:
        pass

    if not opf_path:
        for name in zf.namelist():
            if name.endswith('.opf'):
                opf_path = name
                break

    if not opf_path:
        return [n for n in zf.namelist() if n.endswith(('.html', '.xhtml', '.htm'))]

    try:
        opf_content = zf.read(opf_path).decode('utf-8', errors='ignore')
        opf_dir = str(Path(opf_path).parent)

        manifest = {}
        for m in re.finditer(r'<item[^>]+id="([^"]+)"[^>]+href="([^"]+)"', opf_content):
            manifest[m.group(1)] = m.group(2)

        spine_ids = re.findall(r'<itemref[^>]+idref="([^"]+)"', opf_content)
        files = []
        for idref in spine_ids:
            if idref in manifest:
                href = manifest[idref]
                if opf_dir and opf_dir != '.':
                    href = f"{opf_dir}/{href}"
                if href.endswith(('.html', '.xhtml', '.htm')):
                    files.append(href)
        return files or [n for n in zf.namelist() if n.endswith(('.html', '.xhtml', '.htm'))]
    except Exception:
        return [n for n in zf.namelist() if n.endswith(('.html', '.xhtml', '.htm'))]


def _prioritize_files(files: list[str], front: int = 5, back: int = 3) -> list[str]:
    """Scan front pages, back pages (reversed), then middle."""
    if len(files) <= front + back:
        return files
    return files[:front] + files[-back:][::-1] + files[front:-back]


def extract_from_epub(filepath: str | Path) -> dict:
    """Extract ISBN and DOI from EPUB file content.

    Returns dict with isbn_13, isbn_10, doi, isbn_source, doi_source.
    """
    result: dict = {"isbn_13": None, "isbn_10": None, "doi": None,
                    "isbn_source": None, "doi_source": None}
    try:
        with zipfile.ZipFile(str(filepath), 'r') as zf:
            content_files = _get_epub_spine_files(zf)
            scan_order = _prioritize_files(content_files)

            for fname in scan_order:
                try:
                    raw = zf.read(fname).decode('utf-8', errors='ignore')
                    text = _clean_html(raw)
                except Exception:
                    continue

                if not result["isbn_13"]:
                    isbn13, isbn10 = _find_isbn_in_text(text)
                    if isbn13:
                        result["isbn_13"] = isbn13
                        result["isbn_10"] = isbn10
                        result["isbn_source"] = f"epub_content:{fname}"

                if not result["doi"]:
                    doi = _find_doi_in_text(text)
                    if doi:
                        result["doi"] = doi
                        result["doi_source"] = f"epub_content:{fname}"

                if result["isbn_13"] and result["doi"]:
                    break

    except (zipfile.BadZipFile, OSError) as exc:
        logger.debug("EPUB read error for %s: %s", filepath, exc)

    return result


# ── PDF extraction ───────────────────────────────────────────────────────────

def extract_from_pdf(filepath: str | Path, first_pages: int = 10, last_pages: int = 5) -> dict:
    """Extract ISBN and DOI from PDF content.

    Scans metadata first, then front/back pages.
    """
    result: dict = {"isbn_13": None, "isbn_10": None, "doi": None,
                    "isbn_source": None, "doi_source": None}
    try:
        from pypdf import PdfReader
    except ImportError:
        logger.debug("pypdf not available for PDF extraction")
        return result

    try:
        reader = PdfReader(str(filepath))

        # Check PDF metadata
        if reader.metadata:
            meta_text = ' '.join(str(v) for v in reader.metadata.values() if v)
            isbn13, isbn10 = _find_isbn_in_text(meta_text)
            if isbn13:
                result["isbn_13"] = isbn13
                result["isbn_10"] = isbn10
                result["isbn_source"] = "pdf_metadata"
            doi = _find_doi_in_text(meta_text)
            if doi:
                result["doi"] = doi
                result["doi_source"] = "pdf_metadata"

        if result["isbn_13"] and result["doi"]:
            return result

        # Scan pages
        num_pages = len(reader.pages)
        front = list(range(min(first_pages, num_pages)))
        back_start = max(first_pages, num_pages - last_pages)
        back = list(range(num_pages - 1, back_start - 1, -1)) if num_pages > first_pages else []
        seen = set()
        pages = [p for p in front + back if p not in seen and not seen.add(p)]

        for page_num in pages:
            try:
                text = reader.pages[page_num].extract_text() or ""
            except Exception:
                continue

            if not result["isbn_13"]:
                isbn13, isbn10 = _find_isbn_in_text(text)
                if isbn13:
                    result["isbn_13"] = isbn13
                    result["isbn_10"] = isbn10
                    result["isbn_source"] = f"pdf_page:{page_num + 1}"

            if not result["doi"]:
                doi = _find_doi_in_text(text)
                if doi:
                    result["doi"] = doi
                    result["doi_source"] = f"pdf_page:{page_num + 1}"

            if result["isbn_13"] and result["doi"]:
                break

    except Exception as exc:
        logger.debug("PDF extraction error for %s: %s", filepath, exc)

    return result


# ── Public API ───────────────────────────────────────────────────────────────

def extract_identifiers(filepath: str | Path) -> dict:
    """Extract ISBN and DOI from a book file.

    Supports EPUB and PDF.  Returns dict with:
        isbn_13, isbn_10, doi, isbn_source, doi_source
    """
    filepath = Path(filepath)
    ext = filepath.suffix.lower()

    if ext == '.epub':
        return extract_from_epub(filepath)
    elif ext == '.pdf':
        return extract_from_pdf(filepath)
    else:
        return {"isbn_13": None, "isbn_10": None, "doi": None,
                "isbn_source": None, "doi_source": None}


async def extract_identifiers_for_edition(edition_id: int) -> dict:
    """Extract identifiers for a single edition from its primary file.

    Updates the edition's isbn/isbn_10 and work's doi if found and currently empty.
    Returns the extraction result dict.
    """
    from sqlalchemy import select
    from sqlalchemy.orm import joinedload
    from app.database import get_session_factory
    from app.models.edition import Edition, EditionFile
    from app.models.work import Work

    factory = get_session_factory()
    async with factory() as db:
        result = await db.execute(
            select(Edition)
            .where(Edition.id == edition_id)
            .options(
                joinedload(Edition.files),
                joinedload(Edition.work),
            )
        )
        edition = result.unique().scalar_one_or_none()
        if not edition or not edition.files:
            return {"isbn_13": None, "isbn_10": None, "doi": None}

        # Pick best file (epub preferred over pdf)
        priority = {"epub": 0, "pdf": 1}
        files = sorted(edition.files, key=lambda f: priority.get(f.format.lower(), 99))
        best = files[0]
        fpath = Path(best.file_path)

        if not fpath.exists():
            return {"isbn_13": None, "isbn_10": None, "doi": None}

        import asyncio
        ids = await asyncio.get_event_loop().run_in_executor(None, extract_identifiers, fpath)
        changed = False

        # Update ISBN if edition has none
        if ids["isbn_13"] and not edition.isbn:
            edition.isbn = ids["isbn_13"]
            edition.isbn_10 = ids["isbn_10"]
            changed = True
        elif ids["isbn_10"] and not edition.isbn_10:
            edition.isbn_10 = ids["isbn_10"]
            changed = True

        # Update DOI if work has none
        if ids["doi"] and edition.work and not edition.work.doi:
            edition.work.doi = ids["doi"]
            changed = True

        edition.identifiers_scanned = True
        await db.commit()

        return ids
