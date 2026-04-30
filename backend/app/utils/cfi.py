"""EPUB CFI parsing and cross-format position translation.

EPUB CFI (Canonical Fragment Identifier) is the spec-standard way to
address a position inside an EPUB book. epubjs, foliate, Readium, and
most modern web readers speak it. Kobo Nickel does NOT — it uses
``KoboSpan`` ids inserted into KEPUB chapters by kepubify.

This module provides a focused subset CFI parser and the conversions
the unified-progress emit/restore paths need:

- Web reader → Kobo: ``cfi_to_span_lookup`` (in
  ``app/services/kobo_spans.py``) consumes the parsed CFI's spine_index
  and char_offset to pick the right koboSpan id.
- Kobo → web reader: ``span_to_cfi`` (also in ``kobo_spans.py``) inverts
  the lookup, building a partial CFI that opens the right chapter.

The parser is intentionally narrow:
- Handles wrapper ``epubcfi(...)``.
- Handles range CFIs ``epubcfi(/6/4!/4/2,/1:0,/3:5)`` by taking the
  start half (the conservative choice for resume-here cursors).
- Extracts spine step, in-document path, and char offset.
- Does NOT walk the chapter DOM (would require loading + parsing the
  XHTML). That refinement can land later if exact paragraph round-trip
  becomes necessary.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

# Heuristic chapter-text length used when translating between a koboSpan
# index inside a chapter and a CFI char offset (and vice versa). Real
# chapter lengths vary widely; a fixed 5000 is the same heuristic
# epubjs's locations.generate uses by default and matches the historical
# value this module shipped with.
NOMINAL_CHAPTER_CHARS = 5000


@dataclass
class ParsedCFI:
    """Subset of an EPUB CFI sufficient for our spine + chapter lookups."""

    spine_index: int
    path: list[int] = field(default_factory=list)
    char_offset: int = 0

    @property
    def spine_step(self) -> int:
        """Even-numbered child step under /6 (the package). Inverse of
        ``(spine_step - 2) // 2`` in our spine_index decoding."""
        return (self.spine_index + 1) * 2

    @property
    def in_chapter_fraction(self) -> float:
        """Approximate 0–1 position within the chapter from char offset."""
        if self.char_offset <= 0:
            return 0.0
        return min(1.0, self.char_offset / NOMINAL_CHAPTER_CHARS)


_CFI_WRAPPER = re.compile(r"^\s*epubcfi\s*\((.+)\)\s*$", re.DOTALL)
_SPINE_STEP = re.compile(r"^/6/(\d+)")


def parse_cfi(cfi: Optional[str]) -> Optional[ParsedCFI]:
    """Parse an EPUB CFI into ``ParsedCFI`` or return ``None``.

    Tolerant: returns ``None`` for malformed input rather than raising.
    Range CFIs are reduced to their start position.
    """
    if not cfi:
        return None
    m = _CFI_WRAPPER.match(cfi)
    if not m:
        return None
    body = m.group(1).strip()
    # Range CFI ``/parent,/start,/end`` → take the start.
    if "," in body:
        head, sep, tail = body.partition(",")
        # The first comma separates parent from (start, end). Add the
        # start step back onto the parent path.
        if "," in tail:
            start_step, _ = tail.split(",", 1)
        else:
            start_step = tail
        body = head + start_step

    parts = body.split("!", 1)
    spine_part = parts[0].strip()
    rest = parts[1].strip() if len(parts) > 1 else ""

    spine_m = _SPINE_STEP.match(spine_part)
    if not spine_m:
        return None
    spine_step = int(spine_m.group(1))
    if spine_step < 2 or spine_step % 2 != 0:
        return None
    spine_index = (spine_step - 2) // 2

    path: list[int] = []
    char_offset = 0
    if rest:
        path_part = rest
        # Trailing ``:N`` is the character offset.
        if ":" in rest:
            path_part, _, offset_part = rest.rpartition(":")
            try:
                char_offset = int(offset_part)
            except ValueError:
                char_offset = 0
        for step in path_part.split("/"):
            step = step.strip()
            if not step:
                continue
            try:
                path.append(int(step))
            except ValueError:
                # Skip text-node markers, fragment tokens, etc.
                continue

    return ParsedCFI(spine_index=spine_index, path=path, char_offset=char_offset)


def build_partial_cfi(spine_index: int, in_chapter_fraction: float = 0.0) -> str:
    """Build a partial CFI that opens at a given spine document.

    epubjs accepts partial CFIs that omit the in-document path; the
    rendition opens at the chapter's start. The returned shape includes
    the conventional ``/4/2/1:offset`` body so older readers that
    require a full path also accept it.
    """
    spine_step = (spine_index + 1) * 2
    in_chapter_fraction = max(0.0, min(1.0, in_chapter_fraction))
    char_offset = int(in_chapter_fraction * NOMINAL_CHAPTER_CHARS)
    return f"epubcfi(/6/{spine_step}!/4/2/1:{char_offset})"
