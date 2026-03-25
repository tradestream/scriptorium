"""Text extraction service — converts book files to clean text for analysis.

Integrates techniques from epub2md for high-quality EPUB-to-markdown conversion
with LLM-optimized post-processing (unicode normalization, front matter removal,
footnote simplification, TOC stripping, ligature repair, heading cleanup).

Supports: EPUB, PDF, plain text. Comics return metadata summaries.
PDF extraction uses pdfplumber (with pypdf fallback) for font-aware layout
analysis: heading detection, ligature normalization, page artifact filtering.
"""

import logging
import re
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Book, BookFile

logger = logging.getLogger(__name__)

# Maximum characters before truncation (~50k tokens)
MAX_CHARS = 200_000


# ---------------------------------------------------------------------------
# Unicode normalization mappings (from epub2md/llm_optimize.py)
# ---------------------------------------------------------------------------
UNICODE_REPLACEMENTS = {
    # Smart quotes → straight
    "\u201c": '"', "\u201d": '"',
    "\u2018": "'", "\u2019": "'",
    "\u201a": "'", "\u201e": '"',
    "\u2039": "'", "\u203a": "'",
    "\u00ab": '"', "\u00bb": '"',
    # Dashes
    "\u2014": "--", "\u2013": "-", "\u2212": "-",
    "\u2010": "-", "\u2011": "-",
    # Whitespace oddities
    "\u00a0": " ", "\u2002": " ", "\u2003": " ",
    "\u2009": " ", "\u200a": " ",
    "\u200b": "", "\u2060": "", "\ufeff": "",
    # Punctuation & symbols
    "\u2026": "...",
    "\u2022": "-", "\u00b7": "-",
    "\u25e6": "-", "\u25cf": "-",  # White/black circle bullets
    "\u25a1": "-", "\u25a0": "-",  # White/black square bullets
    "\u2020": "[*]", "\u2021": "[**]",
    "\u00a7": "Section ",
    "\u00b6": "",
    "\u00a9": "(c)", "\u00ae": "(R)", "\u2122": "(TM)",
    # Math
    "\u00b0": " degrees",
    "\u00b1": "+/-",
    "\u00d7": "x",
    "\u00f7": "/",
    "\u2248": "~",
    "\u2260": "!=",
    "\u2264": "<=",
    "\u2265": ">=",
    "\u221e": "infinity",
    # Ligatures (common in PDFs)
    "\ufb01": "fi",   # ﬁ
    "\ufb02": "fl",   # ﬂ
    "\ufb00": "ff",   # ﬀ
    "\ufb03": "ffi",  # ﬃ
    "\ufb04": "ffl",  # ﬄ
    "\ufb05": "st",   # ﬅ
    "\ufb06": "st",   # ﬆ
}


def normalize_unicode(text: str) -> str:
    """Normalize unicode characters to ASCII equivalents for LLM consumption."""
    for char, replacement in UNICODE_REPLACEMENTS.items():
        text = text.replace(char, replacement)
    return text


def simplify_footnotes(text: str) -> str:
    """Simplify HTML-style footnote references to plain text [N]."""
    text = re.sub(r'\[<sup>(\d+)</sup>\]\([^)]*\)', r'[\1]', text)
    text = re.sub(r'<sup>(\d+)</sup>', r'[\1]', text)
    return text


def remove_front_matter(text: str) -> str:
    """Remove copyright, ISBN, and publisher front matter lines."""
    patterns = [
        r'(?i)^cover (?:image|design|art)[:\s]+[^\n]+$',
        r'(?i)^isbn[:\s-]*[\d\-xX]+(?:\s*\([^)]+\))?\s*$',
    ]
    for pattern in patterns:
        text = re.sub(pattern, '', text, flags=re.MULTILINE)
    return text


def remove_toc(text: str) -> str:
    """Remove table-of-contents sections, keeping title lines and actual content."""
    lines = text.split('\n')

    content_start_patterns = [
        r'^#\s+foreword', r'^#\s+preface', r'^#\s+introduction',
        r'^#\s+chapter\s*\d*', r'^#\s+book\s+[ivxlcdm\d]+',
        r'^#\s+part\s+[ivxlcdm\d]+',
        r'^##\s+book\s+[ivxlcdm\d]+', r'^##\s+chapter\s*\d*',
    ]

    content_start_idx = None
    for i, line in enumerate(lines):
        stripped = line.strip().lower()
        for pattern in content_start_patterns:
            if re.match(pattern, stripped, re.IGNORECASE):
                content_start_idx = i
                break
        if content_start_idx is not None:
            break

    if content_start_idx is None:
        return text

    toc_patterns = [
        r'(?i)^#{1,3}\s*(?:table of )?contents?\s*$',
        r'(?i)^#{1,3}\s*list of (?:figures?|tables?|illustrations?)\s*$',
    ]

    result = []
    in_front_section = False

    for i, line in enumerate(lines):
        stripped = line.strip()
        if i < content_start_idx:
            is_toc_header = any(re.match(p, stripped) for p in toc_patterns)
            is_index_header = re.match(
                r'^#{1,3}\s*\**(?:list of |guide|pages|index)', stripped, re.IGNORECASE
            )
            if is_toc_header or is_index_header:
                in_front_section = True
                continue
            if in_front_section:
                continue
            if i < 20 and (stripped.startswith('#') or stripped.startswith('**') or not stripped):
                result.append(line)
            elif i < 20 and len(stripped) < 100:
                result.append(line)
        else:
            result.append(line)

    return '\n'.join(result)


def clean_whitespace(text: str) -> str:
    """Normalize whitespace: collapse blank lines, strip trailing spaces."""
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    text = re.sub(r'\n{3,}', '\n\n', text)
    lines = [line.rstrip() for line in text.split('\n')]
    return '\n'.join(lines).strip()


def clean_internal_links(text: str) -> str:
    """Remove internal EPUB links that won't work outside the EPUB container."""
    text = re.sub(r'\[([^\]]+)\]\([^)]*\.x?html#([^)]+)\)', r'[\1](#\2)', text)
    text = re.sub(r'\[([^\]]+)\]\([^)]*\.x?html\)', r'\1', text)
    return text


def remove_figure_references(text: str) -> str:
    """Remove standalone figure/table caption lines that reference missing images."""
    text = re.sub(
        r'^\s*\*?\*?(?:Figure|Fig\.?|Table|Chart|Illustration|Plate)\s+\d+[\d.]*[:\s]+[^\n]*\*?\*?\s*$',
        '',
        text,
        flags=re.MULTILINE | re.IGNORECASE,
    )
    return text


def clean_heading_hierarchy(text: str) -> str:
    """Remove excessive bold/italic markup from inside heading lines."""
    lines = text.split('\n')
    result = []
    for line in lines:
        heading_match = re.match(r'^(#+)\s+(.+)$', line)
        if heading_match:
            hashes = heading_match.group(1)
            content = heading_match.group(2)
            content = re.sub(r'^\*+\s*', '', content)
            content = re.sub(r'\s*\*+$', '', content)
            result.append(f"{hashes} {content.strip()}")
        else:
            result.append(line)
    return '\n'.join(result)


def fix_hyphenated_linebreaks(text: str) -> str:
    """Rejoin words split by line-break hyphens (common in PDFs and scanned text)."""
    return re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', text)


def optimize_for_llm(
    text: str,
    title: Optional[str] = None,
    author: Optional[str] = None,
) -> str:
    """Apply all LLM optimizations to extracted text.

    Pipeline: normalize unicode → fix hyphenated linebreaks → remove front matter →
    strip TOC → simplify footnotes → clean links → remove figure refs →
    clean heading hierarchy → reduce whitespace → add header.
    """
    text = normalize_unicode(text)
    text = fix_hyphenated_linebreaks(text)
    text = remove_front_matter(text)
    text = remove_toc(text)
    text = simplify_footnotes(text)
    text = clean_internal_links(text)
    text = remove_figure_references(text)
    text = clean_heading_hierarchy(text)
    text = clean_whitespace(text)

    # Add metadata header if available
    header_parts = []
    if title:
        header_parts.append(f"# {title}")
    if author:
        header_parts.append(f"**Author:** {author}")
    if header_parts:
        header = '\n'.join(header_parts)
        if text.strip().startswith('#'):
            first_nl = text.find('\n')
            first_line = text[:first_nl] if first_nl > 0 else text
            if title and title.lower() in first_line.lower():
                text = text[first_nl:].lstrip('\n')
        text = f"{header}\n\n---\n\n{text}"

    return text


def truncate_text(text: str, max_chars: int = MAX_CHARS) -> str:
    """Truncate text at a paragraph boundary, adding a marker."""
    if len(text) <= max_chars:
        return text
    # Try to cut at a paragraph break
    cut = text[:max_chars].rfind('\n\n')
    if cut < max_chars * 0.8:
        cut = max_chars
    return text[:cut] + "\n\n[... text truncated for analysis ...]"


# ---------------------------------------------------------------------------
# Format-specific extractors
# ---------------------------------------------------------------------------

async def _extract_epub_markdown(path: Path) -> str:
    """Extract EPUB to clean markdown using BeautifulSoup + markdownify.

    This is the high-quality path adapted from epub2md/converter.py.
    Produces properly structured markdown with headings, lists, etc.
    """
    try:
        from ebooklib import epub
        from bs4 import BeautifulSoup, Comment
    except ImportError:
        raise RuntimeError(
            "ebooklib and beautifulsoup4 are required. "
            "Run: pip install ebooklib beautifulsoup4"
        )

    try:
        from markdownify import MarkdownConverter
    except ImportError:
        # Fallback to plain text extraction if markdownify isn't available
        logger.warning("markdownify not installed, falling back to plain text extraction")
        return await _extract_epub_plain(path)

    class EnhancedMarkdownConverter(MarkdownConverter):
        """Enhanced converter with heading detection from CSS classes."""

        def convert_p(self, el, text, convert_as_inline=False, parent_tags=None):
            if convert_as_inline:
                return text
            text = text.strip()
            if not text:
                return ''

            classes = el.get('class', [])
            if isinstance(classes, str):
                classes = classes.split()

            is_heading = any('heading' in c.lower() for c in classes)
            is_section = any('h1_heading' in c.lower() or 'h2_heading' in c.lower() for c in classes)

            style = el.get('style', '')
            is_centered = 'text-align:center' in style or 'text-align: center' in style
            is_small_caps = 'font-variant:small-caps' in style

            if is_section:
                return f'**{text}**\n\n'
            if is_heading and (is_centered or is_small_caps):
                return f'# {text}\n\n'

            return f'{text}\n\n'

        def convert_small(self, el, text, convert_as_inline=False, parent_tags=None):
            """Preserve text inside <small> tags — often used for chapter titles."""
            return text.strip() if text else ''

        def convert_sup(self, el, text, convert_as_inline=False, parent_tags=None):
            """Preserve footnote numbers as [N]."""
            text = text.strip()
            if text and text.isdigit():
                return f'[{text}]'
            return f'<sup>{text}</sup>' if text else ''

        def convert_sub(self, el, text, convert_as_inline=False, parent_tags=None):
            text = text.strip()
            return text if text else ''

        def convert_span(self, el, text, convert_as_inline=False, parent_tags=None):
            """Handle spans — preserve text, detect heading classes."""
            text = text.strip() if text else ''
            if not text:
                return ''
            classes = el.get('class', [])
            if isinstance(classes, str):
                classes = classes.split()
            # Some EPUBs use spans with heading classes
            if any('chapter' in c.lower() or 'title' in c.lower() for c in classes):
                return f'**{text}**'
            return text

    book = epub.read_epub(str(path), options={"ignore_ncx": True})
    content_parts = []

    for item in book.get_items():
        if item.media_type == 'application/xhtml+xml':
            soup = BeautifulSoup(item.get_content(), 'html.parser')

            # Strip images, SVGs, comments
            for tag in soup.find_all(['img', 'svg']):
                tag.decompose()
            for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
                comment.extract()

            body = soup.find('body')
            html_content = str(body) if body else str(soup)

            md_content = EnhancedMarkdownConverter(
                heading_style="ATX",
                strip=['script', 'style']
            ).convert(html_content)

            md_content = clean_whitespace(md_content)
            md_content = re.sub(r"<\?xml[^>]*\?>", "", md_content)

            if md_content:
                content_parts.append(md_content)

    return "\n\n".join(content_parts)


async def _extract_epub_plain(path: Path) -> str:
    """Fallback: extract plain text from EPUB using basic HTML parsing."""
    try:
        from ebooklib import epub
        from html.parser import HTMLParser
    except ImportError:
        raise RuntimeError("ebooklib not installed. Run: pip install ebooklib")

    class TextExtractor(HTMLParser):
        def __init__(self):
            super().__init__()
            self.parts: list[str] = []
            self._in_heading = False
            self._in_sup = False
            self._heading_level = 0

        def handle_starttag(self, tag, attrs):
            tag_lower = tag.lower()
            if tag_lower in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
                self._in_heading = True
                self._heading_level = int(tag_lower[1])
                self.parts.append('\n\n' + '#' * self._heading_level + ' ')
            elif tag_lower == 'sup':
                self._in_sup = True
                self.parts.append('[')
            elif tag_lower == 'p':
                self.parts.append('\n\n')
            elif tag_lower == 'br':
                self.parts.append('\n')

        def handle_endtag(self, tag):
            tag_lower = tag.lower()
            if tag_lower in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
                self._in_heading = False
                self.parts.append('\n\n')
            elif tag_lower == 'sup':
                self._in_sup = True
                self.parts.append(']')
                self._in_sup = False

        def handle_data(self, data: str):
            self.parts.append(data)

        def get_text(self) -> str:
            text = "".join(self.parts)
            # Clean up excessive whitespace but preserve paragraph breaks
            text = re.sub(r'\n{3,}', '\n\n', text)
            text = re.sub(r' +', ' ', text)
            return text.strip()

    book = epub.read_epub(str(path), options={"ignore_ncx": True})
    text_parts = []

    for item in book.get_items_of_type(9):  # ITEM_DOCUMENT
        content = item.get_content().decode("utf-8", errors="replace")
        extractor = TextExtractor()
        extractor.feed(content)
        text = extractor.get_text().strip()
        if text:
            text_parts.append(text)

    return "\n\n".join(text_parts)


_PAGE_ARTIFACT_RE = re.compile(
    r'^\s*(?:'
    r'\d{1,4}'                         # bare page number
    r'|page\s+\d+'                     # "Page 42"
    r'|-\s*\d+\s*-'                    # - 42 -
    r'|[ivxlcdm]+'                     # roman numerals
    r'|\[\s*[ivxlcdm]+\s*\]'          # [ xi ]
    r'|[ivxlcdm]+\s*\]'               # Roman with trailing bracket
    r'|\[\s*[ivxlcdm]+'               # Roman with leading bracket
    r'|\[\s*\d+'                       # Partial bracket number: [ 123
    r'|\d+\s*\]'                       # Partial bracket number: 123 ]
    r')\s*$',
    re.IGNORECASE,
)

# Common typographic ligature mappings (from epub2md)
_LIGATURE_MAP = {
    '\ufb01': 'fi', '\ufb02': 'fl', '\ufb00': 'ff',
    '\ufb03': 'ffi', '\ufb04': 'ffl', '\ufb05': 'st', '\ufb06': 'st',
}


def _is_page_artifact(line: str) -> bool:
    return bool(_PAGE_ARTIFACT_RE.match(line.strip()))


def normalize_ligatures(text: str) -> str:
    """Fix ligature characters and broken ligature rendering from PDFs."""
    for lig, repl in _LIGATURE_MAP.items():
        text = text.replace(lig, repl)
    # Fix broken ligature rendering: "fi rst" -> "first", "eff ect" -> "effect"
    for pattern, fix in [
        (r'\bffi\s+([a-z])', r'ffi\1'),
        (r'\bffl\s+([a-z])', r'ffl\1'),
        (r'\bff\s+([a-z])', r'ff\1'),
        (r'\bfi\s+([a-z])', r'fi\1'),
        (r'\bfl\s+([a-z])', r'fl\1'),
        (r'(\w)fi\s+([a-z])', r'\1fi\2'),
        (r'(\w)fl\s+([a-z])', r'\1fl\2'),
        (r'(\w)ff\s+([a-z])', r'\1ff\2'),
    ]:
        text = re.sub(pattern, fix, text)
    return text


def fix_hyphenated_linebreaks(text: str) -> str:
    """Join words split across lines by hyphens: 'word-\\nnext' -> 'wordnext'."""
    return re.sub(r'(\w)-\s*\n\s*(\w)', r'\1\2', text)


async def _extract_pdf_pdfplumber(path: Path) -> str:
    """High-quality PDF extraction using pdfplumber.

    Extracts with font-size metadata → detects headings → filters page
    artifacts → joins continuation lines into proper paragraphs.

    Runs in a thread pool to avoid blocking the event loop.
    """
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _extract_pdf_pdfplumber_sync, path)


def _extract_pdf_pdfplumber_sync(path: Path) -> str:
    """Synchronous pdfplumber extraction (runs in thread pool)."""
    import pdfplumber
    from collections import Counter

    all_lines: list[tuple[str, float]] = []  # (text, font_size)

    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            words = page.extract_words(
                x_tolerance=3,
                y_tolerance=3,
                keep_blank_chars=False,
                use_text_flow=False,
                extra_attrs=["size"],
            )
            if not words:
                continue

            # Group words into lines by top-coordinate
            lines_map: dict[float, list] = {}
            for w in words:
                key = round(w["top"], 1)
                lines_map.setdefault(key, []).append(w)

            for y in sorted(lines_map):
                line_words = sorted(lines_map[y], key=lambda w: w["x0"])
                line_text = " ".join(w["text"] for w in line_words)
                avg_size = sum(w.get("size", 12) for w in line_words) / len(line_words)
                all_lines.append((line_text, avg_size))

    if not all_lines:
        return ""

    # Determine base (body) font size from the most common size
    size_counts: Counter = Counter(round(s, 1) for _, s in all_lines)
    body_size = size_counts.most_common(1)[0][0] if size_counts else 12.0

    # Convert lines to markdown
    result_parts: list[str] = []
    seen_short: set[str] = set()  # for repeated header/footer detection
    paragraph_lines: list[str] = []

    def flush_paragraph() -> None:
        if paragraph_lines:
            result_parts.append(" ".join(paragraph_lines))
            paragraph_lines.clear()

    for line_text, font_size in all_lines:
        stripped = line_text.strip()
        if not stripped:
            flush_paragraph()
            continue

        if _is_page_artifact(stripped):
            continue

        # Repeated short lines are likely running headers/footers
        if len(stripped) < 80:
            if stripped in seen_short:
                continue
            seen_short.add(stripped)

        ratio = font_size / body_size if body_size else 1.0

        if ratio >= 1.4:
            flush_paragraph()
            result_parts.append(f"# {stripped}")
        elif ratio >= 1.2:
            flush_paragraph()
            result_parts.append(f"## {stripped}")
        elif ratio >= 1.05:
            flush_paragraph()
            result_parts.append(f"### {stripped}")
        else:
            # Accumulate body lines into paragraphs
            if paragraph_lines:
                prev = paragraph_lines[-1]
                # Start a new paragraph if the previous line ended with sentence-end
                if prev[-1] in '.!?' and stripped[0].isupper():
                    flush_paragraph()
            paragraph_lines.append(stripped)

    flush_paragraph()
    text = "\n\n".join(result_parts)
    text = normalize_ligatures(text)
    text = fix_hyphenated_linebreaks(text)
    return text


async def _extract_pdf_text(path: Path) -> str:
    """Extract text from a PDF, preferring pdfplumber then falling back to pypdf."""
    try:
        return await _extract_pdf_pdfplumber(path)
    except Exception as plumber_err:
        logger.warning("pdfplumber extraction failed (%s), falling back to pypdf", plumber_err)

    try:
        from pypdf import PdfReader
    except ImportError:
        raise RuntimeError(
            "Neither pdfplumber nor pypdf could extract this PDF. "
            "Run: pip install pdfplumber"
        )

    reader = PdfReader(str(path))
    text_parts = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            text_parts.append(text.strip())
    return "\n\n".join(text_parts)


# ---------------------------------------------------------------------------
# Main extraction API
# ---------------------------------------------------------------------------

async def extract_text_from_book(
    book: Book,
    db: AsyncSession,
    *,
    output_format: str = "markdown",
    llm_optimize: bool = True,
    max_chars: int = MAX_CHARS,
) -> str:
    """Extract readable text from a book's primary file.

    Uses cached markdown when available (generated by the markdown service).

    Args:
        book: Book model instance
        db: Database session
        output_format: "markdown" for structured output, "plain" for raw text
        llm_optimize: Apply LLM optimizations (unicode normalization, front matter
            removal, TOC stripping, footnote simplification)
        max_chars: Maximum characters before truncation

    Returns:
        Extracted and (optionally) optimized text string.
    """
    # Check for cached markdown first
    if output_format == "markdown" and llm_optimize:
        try:
            from app.services.markdown import has_cached_markdown, markdown_path_for
            if hasattr(book, 'uuid') and has_cached_markdown(book.uuid):
                text = markdown_path_for(book.uuid).read_text(encoding="utf-8")
                return truncate_text(text, max_chars)
        except Exception:
            pass  # Fall through to live extraction

    stmt = select(BookFile).where(BookFile.edition_id == book.id)
    result = await db.execute(stmt)
    files = result.scalars().all()

    if not files:
        raise ValueError(f"No files found for book '{book.title}'")

    # Prefer text-rich formats
    format_priority = {"epub": 0, "txt": 1, "pdf": 2, "mobi": 3}
    sorted_files = sorted(files, key=lambda f: format_priority.get(f.format.lower(), 99))
    book_file = sorted_files[0]
    from app.config import resolve_path
    file_path = Path(resolve_path(book_file.file_path))

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    fmt = book_file.format.lower()

    # Extract raw text
    if fmt == "epub":
        if output_format == "markdown":
            text = await _extract_epub_markdown(file_path)
        else:
            text = await _extract_epub_plain(file_path)
    elif fmt == "pdf":
        text = await _extract_pdf_text(file_path)
    elif fmt in ("txt", "text"):
        text = file_path.read_text(encoding="utf-8", errors="replace")
    elif fmt in ("cbr", "cbz", "cb7"):
        return (
            f"[Comic: {book.title}]\n"
            f"This is a comic/graphic novel in {fmt.upper()} format. "
            f"Text extraction is not available for image-based formats.\n"
            f"Description: {book.description or 'No description available.'}"
        )
    else:
        raise ValueError(f"Unsupported format for text extraction: {fmt}")

    # Apply LLM optimizations
    if llm_optimize:
        # Get author name for header if available
        author_name = None
        if hasattr(book, 'authors') and book.authors:
            author_name = book.authors[0].name if book.authors else None

        text = optimize_for_llm(
            text,
            title=book.title,
            author=author_name,
        )

    # Truncate if needed
    text = truncate_text(text, max_chars)

    return text
