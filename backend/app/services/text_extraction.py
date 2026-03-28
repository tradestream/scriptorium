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
    """Normalize whitespace: collapse blank lines, strip trailing spaces, merge tiny sections."""
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    text = re.sub(r'\n{3,}', '\n\n', text)
    lines = [line.rstrip() for line in text.split('\n')]
    text = '\n'.join(lines).strip()

    # Merge tiny orphan sections into neighbors
    # Splits on double-newline, merges sections <50 chars into previous section
    parts = text.split('\n\n')
    merged = []
    for part in parts:
        if not part.strip():
            continue
        if merged and len(part.strip()) < 50 and not part.strip().startswith('#'):
            merged[-1] = merged[-1] + ' ' + part.strip()
        else:
            merged.append(part)
    return '\n\n'.join(merged)


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


async def _extract_epub_poetry(path: Path) -> str:
    """Extract EPUB preserving verse line structure.

    In poetry EPUBs, each <p> is a line of verse, not a paragraph.
    This extractor:
    - Treats each <p> as a single line (\\n not \\n\\n)
    - Detects stanza breaks via empty <p> or blank lines
    - Detects author headings (ALL CAPS + spaced letters)
    - Preserves poem titles as markdown headings
    - Strips line numbers (5, 10, 15, etc.)
    """
    try:
        from ebooklib import epub
        from bs4 import BeautifulSoup, Comment
    except ImportError:
        raise RuntimeError("ebooklib and beautifulsoup4 required")

    # Track whether we've passed front matter
    _past_front_matter = [False]
    _front_matter_end_markers = {'caedmon', 'anonymous', 'beowulf', 'riddles',
                                  'prologue', 'book i', 'canto i', 'part i'}

    def _is_author_heading(text: str) -> bool:
        """Detect poet name headings like 'R O B E R T  F R O S T' or 'ROBERT FROST'.

        Must be: letter-spaced ALL CAPS personal name (2-4 words)
        or regular ALL CAPS name. Excludes institutions, boilerplate, single words.
        """
        stripped = text.strip()
        if not stripped or len(stripped) < 5:
            return False

        # Detect and collapse letter-spaced text
        # "R O B E R T  F R O S T" → check if it's a name
        parts = stripped.split()
        single_chars = sum(1 for p in parts if len(p) == 1 and p.isalpha())
        is_letter_spaced = single_chars > len(parts) * 0.5 and len(parts) > 4

        if is_letter_spaced:
            # Collapse: group runs of single letters into words
            collapsed_words = []
            buf = []
            for p in parts:
                if len(p) == 1 and p.isalpha():
                    buf.append(p)
                else:
                    if buf:
                        collapsed_words.append(''.join(buf))
                        buf = []
                    collapsed_words.append(p)
            if buf:
                collapsed_words.append(''.join(buf))

            name = ' '.join(collapsed_words).upper()
            # Must be 2-4 words, all alpha (personal name, not institution)
            if 2 <= len(collapsed_words) <= 5 and all(w.isalpha() for w in collapsed_words):
                # Exclude institutional words
                institutional = {'university', 'college', 'professor', 'emeritus',
                                 'institute', 'edition', 'late', 'oxford', 'cambridge'}
                if not any(w.lower() in institutional for w in collapsed_words):
                    return True
            return False

        # Regular ALL CAPS: "ROBERT FROST" — 2-4 words, all alpha
        words = stripped.split()
        if (stripped.isupper() and 2 <= len(words) <= 5
                and all(w.isalpha() or w in ('.', '-', "'") for w in words)):
            # Exclude boilerplate
            boilerplate = {'CONTENTS', 'COPYRIGHT', 'ACKNOWLEDGMENTS', 'PERMISSIONS',
                          'INDEX', 'NOTES', 'PREFACE', 'INTRODUCTION', 'GLOSSARY',
                          'PRINTED', 'ALL RIGHTS', 'EDITORS EMERITI', 'NEW YORK',
                          'FIFTH EDITION', 'SHORTER EDITION'}
            if stripped in boilerplate or any(b in stripped for b in boilerplate):
                return False
            # Exclude if any word is an institutional term
            institutional = {'UNIVERSITY', 'COLLEGE', 'PROFESSOR', 'EMERITUS',
                           'INSTITUTE', 'EDITION', 'COMPANY', 'NORTON', 'PRESS'}
            if any(w in institutional for w in words):
                return False
            return True
        return False

    def _is_date_line(text: str) -> bool:
        """Detect standalone date lines like '1874-1963' or 'b. 1931'."""
        return bool(re.match(r'^\s*(?:b\.\s*)?\d{4}\s*[-–]\s*\d{0,4}\s*$', text.strip()))

    def _is_poem_title(text: str, prev_was_blank: bool = False) -> bool:
        """Detect poem titles — must follow a blank line and look like a title, not verse.

        Key heuristic: poem titles appear AFTER stanza/poem breaks (blank lines)
        and do NOT end with verse-continuation punctuation.
        """
        stripped = text.strip()
        if not stripped or len(stripped) > 60:
            return False
        # Must follow a blank line (titles come after poem breaks)
        if not prev_was_blank:
            return False
        # Must not end with verse punctuation (comma, semicolon, colon, dash)
        if stripped[-1] in ',;:—-':
            return False
        # Must not end with period unless very short (abbreviations in titles)
        if stripped.endswith('.') and len(stripped) > 20:
            return False
        # Must not contain line-number-like starts
        if re.match(r'^\d+\s', stripped):
            return False
        # Must be mostly capitalized words (Title Case)
        words = stripped.split()
        if len(words) > 8:
            return False
        cap_words = sum(1 for w in words if w[0:1].isupper() or w.lower() in {'a', 'an', 'the', 'of', 'in', 'on', 'to', 'for', 'and', 'or', 'but'})
        if cap_words / len(words) < 0.5:
            return False
        # Skip common boilerplate
        if any(skip in stripped.upper() for skip in ['CONTENTS', 'COPYRIGHT', 'PRINTED', 'COMPOSITION', 'ALL RIGHTS']):
            return False
        return True

    def _is_line_number(text: str) -> bool:
        """Detect line numbers (5, 10, 15, etc.) and roman numeral line numbers."""
        stripped = text.strip()
        if re.match(r'^\d{1,3}$', stripped):
            return int(stripped) % 5 == 0 or int(stripped) <= 3
        # "io" = 10, common OCR
        if stripped.lower() in ('io', 'ii', 'iii', 'iv', 'v', 'vi', 'vii', 'viii', 'ix', 'x'):
            return True
        return False

    book = epub.read_epub(str(path), options={"ignore_ncx": True})
    output_lines = []
    current_author = ""
    file_count = 0

    for item in book.get_items():
        if item.media_type != 'application/xhtml+xml':
            continue

        # Insert poem/section separator between EPUB files
        file_count += 1
        if file_count > 1 and output_lines:
            # Triple newline = poem break (distinct from double = stanza break)
            output_lines.append('')
            output_lines.append('---')
            output_lines.append('')

        soup = BeautifulSoup(item.get_content(), 'html.parser')
        for tag in soup.find_all(['img', 'svg', 'script', 'style']):
            tag.decompose()
        for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
            comment.extract()

        body = soup.find('body') or soup

        prev_was_blank = True  # Start of file counts as blank

        for el in body.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'div', 'br']):
            tag_name = el.name.lower()

            # Headings → markdown headings
            if tag_name in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
                level = int(tag_name[1])
                text = el.get_text(strip=True)
                if text:
                    output_lines.append('')
                    output_lines.append(f'{"#" * level} {text}')
                    output_lines.append('')
                    prev_was_blank = True
                continue

            # BR → line break
            if tag_name == 'br':
                output_lines.append('')
                prev_was_blank = True
                continue

            text = el.get_text(strip=True)
            if not text:
                # Empty <p> = stanza break
                output_lines.append('')
                prev_was_blank = True
                continue

            # Strip inline line numbers at start
            text = re.sub(r'^\d{1,3}\s+', '', text)
            # Strip trailing page numbers
            text = re.sub(r'\s+\d{3,4}\s*$', '', text)

            # Detect special elements
            if _is_author_heading(text):
                collapsed = text.replace(' ', '') if text.count(' ') > len(text.replace(' ', '')) * 0.5 else text
                current_author = collapsed.title() if collapsed.isupper() else collapsed
                output_lines.append('')
                output_lines.append(f'## {current_author}')
                output_lines.append('')
                continue

            if _is_date_line(text):
                # Append to author heading
                if output_lines and output_lines[-1] == '':
                    output_lines[-2] = f'{output_lines[-2]} ({text.strip()})'
                continue

            if _is_line_number(text):
                continue

            # Check if this looks like a poem title (before a verse block)
            if _is_poem_title(text, prev_was_blank):
                output_lines.append('')
                output_lines.append(f'### {text}')
                output_lines.append('')
                prev_was_blank = True
                continue

            # Bold text often = date or special marker
            bold = el.find('b')
            if bold and not el.find('b').find_next_sibling():
                bold_text = bold.get_text(strip=True)
                if re.match(r'^\d{4}$', bold_text):
                    # Year marker — end of poem
                    output_lines.append('')
                    continue

            # Regular line of verse
            # Preserve italic markers
            for i_tag in el.find_all('i'):
                i_tag.replace_with(f'*{i_tag.get_text()}*')
            for b_tag in el.find_all('b'):
                b_tag.replace_with(f'**{b_tag.get_text()}**')

            final_text = el.get_text()
            # Strip leading line numbers again (may be inline)
            final_text = re.sub(r'^\s*\d{1,3}\s{2,}', '', final_text)
            final_text = final_text.rstrip()

            if final_text:
                output_lines.append(final_text)
                prev_was_blank = False
            else:
                prev_was_blank = True

    # Clean up
    text = '\n'.join(output_lines)

    # Strip front matter using heuristic: find where verse content begins
    # Verse lines are short (< 80 chars). TOC/front matter lines are long.
    # Find the first stretch of 5+ consecutive short lines (= actual poetry)
    text_lines = text.split('\n')
    verse_start = 0
    consecutive_short = 0
    for i, line in enumerate(text_lines):
        stripped = line.strip()
        if stripped and 5 < len(stripped) < 80 and not stripped.startswith('#'):
            consecutive_short += 1
            if consecutive_short >= 5:
                verse_start = max(0, i - consecutive_short)
                break
        else:
            consecutive_short = 0

    if verse_start > 20:
        text = '\n'.join(text_lines[verse_start:])

    # Collapse 3+ blank lines to 2 (stanza break), preserve single newlines (line breaks)
    text = re.sub(r'\n{4,}', '\n\n\n', text)
    text = normalize_unicode(text)
    return text.strip()


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


def _extract_pdf_marker(path: Path) -> str:
    """High-quality PDF extraction using Marker (ML-based).

    Preserves bold, italic, headings, tables, footnotes.
    Works on CPU (slower) or GPU/MPS (fast).
    Falls back to pdfplumber if Marker is not installed or fails.

    Uses subprocess to avoid threading issues with torch on some platforms.
    """
    import subprocess
    import sys
    import shutil

    # Check if marker CLI is available
    marker_bin = shutil.which("marker")
    if not marker_bin:
        logger.debug("Marker CLI not found, falling back to pdfplumber")
        return _extract_pdf_pdfplumber_sync(path)

    try:
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [sys.executable, "-c", f"""
import sys
try:
    from marker.converters.pdf import PdfConverter
    from marker.config.parser import ConfigParser
    config = ConfigParser({{"output_format": "markdown"}})
    converter = PdfConverter(config=config.generate_config_dict())
    result = converter("{path}")
    print(result.markdown)
except Exception as e:
    print(f"MARKER_ERROR: {{e}}", file=sys.stderr)
    sys.exit(1)
"""],
                capture_output=True, text=True, timeout=600,
                env={**__import__('os').environ, 'OMP_NUM_THREADS': '1'},
            )

            if result.returncode == 0 and result.stdout and len(result.stdout.strip()) > 200:
                logger.info("Marker extracted %d chars from %s", len(result.stdout), path.name)
                return result.stdout
            else:
                logger.warning("Marker failed for %s (rc=%d), falling back to pdfplumber",
                               path.name, result.returncode)
                return _extract_pdf_pdfplumber_sync(path)

    except subprocess.TimeoutExpired:
        logger.warning("Marker timed out for %s, falling back to pdfplumber", path.name)
        return _extract_pdf_pdfplumber_sync(path)
    except Exception as e:
        logger.warning("Marker error for %s: %s, falling back to pdfplumber", path.name, e)
        return _extract_pdf_pdfplumber_sync(path)


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
    """Synchronous pdfplumber extraction with page-level optimization."""
    import pdfplumber
    from collections import Counter

    def _process_page(page):
        """Extract lines from a single page."""
        words = page.extract_words(
            x_tolerance=3, y_tolerance=3,
            keep_blank_chars=False, use_text_flow=False,
            extra_attrs=["size"],
        )
        if not words:
            return []
        lines_map: dict[float, list] = {}
        for w in words:
            lines_map.setdefault(round(w["top"], 1), []).append(w)
        page_lines = []
        for y in sorted(lines_map):
            lw = sorted(lines_map[y], key=lambda w: w["x0"])
            page_lines.append((" ".join(w["text"] for w in lw),
                               sum(w.get("size", 12) for w in lw) / len(lw)))
        return page_lines

    all_lines: list[tuple[str, float]] = []

    with pdfplumber.open(str(path)) as pdf:
        # Process pages — pdfplumber isn't thread-safe so sequential,
        # but the per-page function is optimized
        for page in pdf.pages:
            all_lines.extend(_process_page(page))

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

    def _is_spaced_out(text: str) -> bool:
        """Detect letter-spaced text like 'S E T H' or 'A R G U M E N T'."""
        # If most characters are single letters separated by spaces
        parts = text.split()
        if len(parts) < 3:
            return False
        single_chars = sum(1 for p in parts if len(p) <= 2)
        return single_chars / len(parts) > 0.6

    def _collapse_spacing(text: str) -> str:
        """Collapse 'S E T H' → 'SETH', 'A R G U M E N T' → 'ARGUMENT'."""
        parts = text.split()
        if all(len(p) <= 2 for p in parts):
            return ''.join(parts)
        # Mixed: collapse runs of single chars, keep multi-char words
        result = []
        buffer = []
        for p in parts:
            if len(p) <= 2 and p.isalpha():
                buffer.append(p)
            else:
                if buffer:
                    result.append(''.join(buffer))
                    buffer = []
                result.append(p)
        if buffer:
            result.append(''.join(buffer))
        return ' '.join(result)

    def _is_likely_heading(stripped: str, ratio: float) -> bool:
        """Conservative heading detection to reduce false positives.

        Only classify as heading if: large enough font AND short AND looks like a title.
        """
        if ratio < 1.05:
            return False
        # Must be short — real headings rarely exceed 80 chars
        if len(stripped) > 80:
            return False
        # Skip if it contains multiple sentences (body text with larger font)
        if stripped.count('.') > 1:
            return False
        # Skip if it contains common sentence-interior punctuation
        if ',' in stripped and len(stripped) > 50:
            return False
        # Skip if it starts lowercase (continuation text)
        if stripped[0].islower():
            return False
        # Skip footnote/reference numbers
        if re.match(r'^\d+[\.\)]\s', stripped) and len(stripped) > 40:
            return False
        # Require significantly larger font for short-ish text to be a heading
        if ratio < 1.15 and len(stripped) > 60:
            return False
        # Skip very short fragments (single words, numbers, Greek/Latin fragments)
        if len(stripped) < 4:
            return False
        # Skip if mostly non-alpha (punctuation, numbers)
        alpha_ratio = sum(1 for c in stripped if c.isalpha()) / max(len(stripped), 1)
        if alpha_ratio < 0.5:
            return False
        return True

    for line_text, font_size in all_lines:
        stripped = line_text.strip()
        if not stripped:
            flush_paragraph()
            continue

        if _is_page_artifact(stripped):
            continue

        # Fix letter-spaced text from title pages
        if _is_spaced_out(stripped):
            stripped = _collapse_spacing(stripped)

        # Repeated short lines are likely running headers/footers
        if len(stripped) < 80:
            if stripped in seen_short:
                continue
            seen_short.add(stripped)

        ratio = font_size / body_size if body_size else 1.0

        if _is_likely_heading(stripped, ratio):
            flush_paragraph()
            if ratio >= 1.4:
                result_parts.append(f"# {stripped}")
            elif ratio >= 1.2:
                result_parts.append(f"## {stripped}")
            else:
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
    # Clean up soft hyphens and broken hyphenation
    text = text.replace('\u00ad', '')  # soft hyphen
    text = re.sub(r'(\w)­\s*\n\s*(\w)', r'\1\2', text)  # hyphen at line break
    return text


async def _extract_pdf_text(path: Path) -> str:
    """Extract text from a PDF. Priority: Marker → pdfplumber → pypdf."""
    # Try Marker first (ML-based, preserves formatting)
    try:
        loop = __import__('asyncio').get_event_loop()
        text = await loop.run_in_executor(None, _extract_pdf_marker, path)
        if text and len(text.strip()) > 200:
            return text
    except Exception as marker_err:
        logger.debug("Marker extraction failed (%s), trying pdfplumber", marker_err)

    # Fallback: pdfplumber
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
            from app.services.markdown import has_cached_markdown, markdown_path_for, strip_yaml_frontmatter
            if hasattr(book, 'uuid') and has_cached_markdown(book.uuid):
                text = strip_yaml_frontmatter(markdown_path_for(book.uuid).read_text(encoding="utf-8"))
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


# ── Sync wrappers for background threads ─────────────────────────


def _extract_epub_poetry_sync(path: Path) -> str:
    """Sync wrapper for poetry-aware EPUB extraction."""
    import asyncio
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_extract_epub_poetry(path))
    finally:
        loop.close()


def _extract_epub_markdown_sync(path: Path) -> str:
    """Sync wrapper — _extract_epub_markdown is async in name only (no awaits)."""
    import asyncio
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_extract_epub_markdown(path))
    finally:
        loop.close()
