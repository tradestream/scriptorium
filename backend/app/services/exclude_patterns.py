"""Glob-based exclusion for library scans + ingest.

Used by the library scanner and ingest watcher to skip junk before the
expensive hash / metadata / FTS pipeline runs. Three sources are merged
in priority order:

  1. ``DEFAULT_EXCLUDE_PATTERNS`` — OS / sync-tool noise that nobody
     ever wants to ingest. Always applied.
  2. ``Library.exclude_patterns`` — per-library JSON list.
  3. ``.scriptoriumignore`` — gitignore-style file at the library root.

The built-in defaults are intentionally conservative — they catch the
common broken-import sources (``__MACOSX`` Apple metadata folders,
Synology ``@eaDir`` thumbnail dirs, half-downloaded ``*.crdownload``
files) without rejecting anything a user might legitimately want to
keep.

Patterns are POSIX globs evaluated by ``fnmatch.fnmatchcase`` against
the path *relative to the library root*, plus the bare basename. That
keeps ``**/backup/**`` and ``*.tmp`` both intuitive: the first matches
any file inside a backup directory at any depth, the second matches
any file with that extension regardless of nesting.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Iterable, Optional

logger = logging.getLogger(__name__)


# Always-applied defaults. Edit this list with care: anything added here
# silently affects every existing library on the next scan.
DEFAULT_EXCLUDE_PATTERNS: list[str] = [
    # macOS
    "**/.DS_Store",
    "**/.AppleDouble/**",
    "**/__MACOSX/**",
    "**/.Spotlight-V100/**",
    "**/.Trashes/**",
    # Synology DSM
    "**/@eaDir/**",
    "**/#recycle/**",
    # Common backup folders
    "**/backup/**",
    "**/.bak/**",
    # Partial / interrupted downloads
    "**/*.tmp",
    "**/*.part",
    "**/*.partial",
    "**/*.crdownload",
    "**/*.download",
    # Editor / archive artifacts
    "**/.~lock.*",
    "**/Thumbs.db",
]

# Convert ``**`` recursive globs into something ``fnmatch`` understands.
# ``fnmatch`` doesn't treat ``**`` as "any depth"; we translate it to a
# regex per pattern at load time. POSIX path separators only — Path's
# ``as_posix()`` normalises Windows backslashes for us.
_DOUBLE_STAR_RE = re.compile(r"\*\*/?")


def _glob_to_regex(pattern: str) -> re.Pattern[str]:
    """Translate a gitignore-style glob to a regex anchored at ``^...$``.

    ``**`` means "any number of path segments"; ``*`` means "any
    sequence of non-slash chars"; ``?`` means "one non-slash char".
    Everything else is treated as a literal.
    """
    # Replace ``**/`` first, then ``**`` alone (trailing).
    # We work in three passes so ``**`` doesn't interleave with single-``*``.
    placeholder_double = "\x00DSTAR\x00"
    placeholder_single = "\x00SSTAR\x00"
    placeholder_q = "\x00QMARK\x00"
    s = pattern
    s = s.replace("**/", placeholder_double + "/")
    s = s.replace("**", placeholder_double)
    s = s.replace("*", placeholder_single)
    s = s.replace("?", placeholder_q)
    s = re.escape(s)
    s = s.replace(re.escape(placeholder_double + "/"), "(?:.*/)?")
    s = s.replace(re.escape(placeholder_double), ".*")
    s = s.replace(re.escape(placeholder_single), "[^/]*")
    s = s.replace(re.escape(placeholder_q), "[^/]")
    return re.compile(f"^{s}$")


class PatternMatcher:
    """Compile-once matcher reused across many path checks per scan."""

    def __init__(self, patterns: Iterable[str]):
        self._regexes: list[re.Pattern[str]] = []
        seen: set[str] = set()
        for raw in patterns:
            p = (raw or "").strip()
            if not p or p.startswith("#") or p in seen:
                continue
            seen.add(p)
            try:
                self._regexes.append(_glob_to_regex(p))
            except re.error as exc:
                logger.warning("exclude_patterns: bad pattern %r: %s", p, exc)

    def matches(self, posix_path: str) -> bool:
        """True if ``posix_path`` (forward-slash relative path or basename)
        matches any compiled pattern.
        """
        for regex in self._regexes:
            if regex.match(posix_path):
                return True
        return False

    def __bool__(self) -> bool:
        return bool(self._regexes)


def _parse_library_patterns(library_exclude_json: Optional[str]) -> list[str]:
    if not library_exclude_json:
        return []
    try:
        parsed = json.loads(library_exclude_json)
    except (TypeError, ValueError):
        return []
    if not isinstance(parsed, list):
        return []
    return [str(p) for p in parsed if isinstance(p, (str, int, float))]


def _parse_ignore_file(library_root: Path) -> list[str]:
    """Read ``.scriptoriumignore`` (gitignore-style) at the library root.

    Returns ``[]`` if the file is missing or unreadable. Comments
    (``#``) and blank lines are stripped.
    """
    ignore_file = library_root / ".scriptoriumignore"
    if not ignore_file.is_file():
        return []
    try:
        text = ignore_file.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    out: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        out.append(stripped)
    return out


def build_matcher(
    library_root: Path,
    library_exclude_json: Optional[str],
) -> PatternMatcher:
    """Compile defaults + library + ``.scriptoriumignore`` patterns once."""
    patterns = list(DEFAULT_EXCLUDE_PATTERNS)
    patterns.extend(_parse_library_patterns(library_exclude_json))
    patterns.extend(_parse_ignore_file(library_root))
    return PatternMatcher(patterns)


def is_excluded(
    file_path: Path,
    library_root: Path,
    matcher: PatternMatcher,
) -> bool:
    """Check whether ``file_path`` should be skipped.

    Matched against both the path *relative to the library root* and
    the bare basename, so glob authors can write either ``*.tmp`` or
    ``**/backup/**`` and have it work the way they expect.
    """
    if not matcher:
        return False
    try:
        rel = file_path.relative_to(library_root).as_posix()
    except ValueError:
        # file_path is outside library_root — defensive; shouldn't
        # happen from the scanner, but if it does treat the basename
        # as the only key.
        rel = file_path.name
    return matcher.matches(rel) or matcher.matches(file_path.name)
