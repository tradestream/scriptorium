"""Book file naming pattern resolver (Booklore-compatible).

Pattern syntax:
  {title}         — book title
  {author}        — first author
  {authors}       — all authors, comma-separated
  {year}          — publication year (YYYY)
  {series}        — first series name
  {series_index}  — series position, zero-padded to 2 digits (e.g. "03")
  {language}      — language code (e.g. "en")
  {publisher}     — publisher name
  {isbn}          — ISBN-13 or ISBN-10

Optional blocks: wrap in < > — the entire block is dropped if any placeholder
inside it has no value.
  <{series}/><{series_index}. >{title}
    → "Dune Chronicles/01. Dune" when series is set
    → "Dune" when series is absent

A trailing / is stripped.
The file extension is always appended automatically.

Default pattern:  {authors}/{title}
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

_OPT_BLOCK = re.compile(r"<([^>]*)>")
_PLACEHOLDER = re.compile(r"\{(\w+)\}")

# Characters illegal in filenames on Windows/Linux/macOS
_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

DEFAULT_PATTERN = "{authors}/{title}"


def _sanitize(value: str) -> str:
    """Strip characters that are illegal in filesystem names."""
    value = _ILLEGAL.sub("_", value)
    value = value.strip(". ")          # no leading/trailing dots or spaces
    # Collapse multiple consecutive spaces/underscores
    value = re.sub(r"_+", "_", value)
    value = re.sub(r" +", " ", value)
    return value or "_"


def _build_context(
    title: str,
    authors: list[str],
    year: Optional[int] = None,
    series: Optional[str] = None,
    series_index: Optional[float] = None,
    language: Optional[str] = None,
    publisher: Optional[str] = None,
    isbn: Optional[str] = None,
) -> dict[str, str]:
    first_author = authors[0] if authors else ""
    all_authors = ", ".join(authors) if authors else ""

    # Format series index: whole numbers as zero-padded "01", floats as "01.5"
    si = ""
    if series_index is not None:
        if series_index == int(series_index):
            si = f"{int(series_index):02d}"
        else:
            si = f"{series_index:04.1f}"

    return {
        "title": _sanitize(title) if title else "Unknown Title",
        "author": _sanitize(first_author),
        "authors": _sanitize(all_authors) if all_authors else "Unknown Author",
        "year": str(year) if year else "",
        "series": _sanitize(series) if series else "",
        "series_index": si,
        "language": _sanitize(language) if language else "",
        "publisher": _sanitize(publisher) if publisher else "",
        "isbn": isbn or "",
    }


def _resolve(pattern: str, ctx: dict[str, str]) -> str:
    def process_optional(m: re.Match) -> str:
        inner = m.group(1)
        placeholders = _PLACEHOLDER.findall(inner)
        if any(not ctx.get(p, "").strip() for p in placeholders):
            return ""
        return _PLACEHOLDER.sub(lambda x: ctx.get(x.group(1), ""), inner)

    result = _OPT_BLOCK.sub(process_optional, pattern)
    result = _PLACEHOLDER.sub(lambda m: ctx.get(m.group(1), ""), result)
    return result


def build_relative_path(
    pattern: str,
    title: str,
    authors: list[str],
    file_ext: str,
    *,
    year: Optional[int] = None,
    series: Optional[str] = None,
    series_index: Optional[float] = None,
    language: Optional[str] = None,
    publisher: Optional[str] = None,
    isbn: Optional[str] = None,
) -> Path:
    """Return a relative path (directories + filename + extension) from a pattern.

    Example:
        build_relative_path(
            "{authors}/{title}",
            "Blood Meridian", ["Cormac McCarthy"], ".epub"
        )
        → Path("Cormac McCarthy/Blood Meridian.epub")
    """
    ctx = _build_context(
        title=title,
        authors=authors,
        year=year,
        series=series,
        series_index=series_index,
        language=language,
        publisher=publisher,
        isbn=isbn,
    )

    resolved = _resolve(pattern, ctx).rstrip("/").strip()
    if not resolved:
        resolved = _sanitize(title) or "Unknown"

    # Split on forward slash to get directory parts + filename stem
    parts = [p.strip() for p in resolved.split("/") if p.strip()]
    if not parts:
        parts = [_sanitize(title) or "Unknown"]

    *dirs, stem = parts

    ext = file_ext if file_ext.startswith(".") else f".{file_ext}"
    filename = stem + ext

    return Path(*dirs, filename) if dirs else Path(filename)


def preview(pattern: str) -> str:
    """Return an example resolved path string for display in settings UI."""
    return str(build_relative_path(
        pattern,
        title="The Way of Kings",
        authors=["Brandon Sanderson"],
        file_ext=".epub",
        year=2010,
        series="The Stormlight Archive",
        series_index=1,
        publisher="Tor Books",
        isbn="9780765326355",
        language="en",
    ))
