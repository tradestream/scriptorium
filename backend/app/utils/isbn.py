"""ISBN detection, validation, and normalization utilities.

Canonical storage format is ISBN-13.  ISBN-10 is kept as an optional cache
for external API lookups (OpenLibrary, Google Books, used-book marketplaces).
"""

import re

_STRIP_RE = re.compile(r"[\s\-]+")


def clean(raw: str) -> str:
    """Strip hyphens, spaces, and surrounding whitespace."""
    return _STRIP_RE.sub("", raw.strip())


def is_isbn10(value: str) -> bool:
    """Return True if *value* looks like a valid ISBN-10 (after cleaning)."""
    v = clean(value)
    if len(v) != 10:
        return False
    # First 9 must be digits, last may be digit or 'X'
    return v[:9].isdigit() and (v[9].isdigit() or v[9] in "xX")


def is_isbn13(value: str) -> bool:
    """Return True if *value* looks like a valid ISBN-13 (after cleaning)."""
    v = clean(value)
    return len(v) == 13 and v.isdigit()


def validate_isbn10_checksum(value: str) -> bool:
    """Verify the ISBN-10 check digit."""
    v = clean(value)
    if not is_isbn10(v):
        return False
    total = 0
    for i, ch in enumerate(v[:9]):
        total += int(ch) * (10 - i)
    last = v[9]
    total += 10 if last in "xX" else int(last)
    return total % 11 == 0


def validate_isbn13_checksum(value: str) -> bool:
    """Verify the ISBN-13 check digit."""
    v = clean(value)
    if not is_isbn13(v):
        return False
    total = sum(int(ch) * (1 if i % 2 == 0 else 3) for i, ch in enumerate(v))
    return total % 10 == 0


def isbn10_to_isbn13(isbn10: str) -> str:
    """Convert an ISBN-10 to ISBN-13.

    Prefixes with '978', drops the old check digit, and recalculates.
    """
    v = clean(isbn10)
    if len(v) != 10:
        raise ValueError(f"Not a 10-digit ISBN: {isbn10!r}")
    base = "978" + v[:9]
    check = _isbn13_check_digit(base)
    return base + str(check)


def isbn13_to_isbn10(isbn13: str) -> str | None:
    """Convert an ISBN-13 back to ISBN-10 if it has a 978 prefix.

    Returns None for 979-prefix ISBNs (no ISBN-10 equivalent).
    """
    v = clean(isbn13)
    if len(v) != 13 or not v.startswith("978"):
        return None
    base = v[3:12]
    check = _isbn10_check_digit(base)
    return base + check


def normalize(raw: str) -> tuple[str | None, str | None]:
    """Normalize an ISBN string to (isbn_13, isbn_10).

    Accepts either format.  Returns (None, None) for invalid input.
    """
    v = clean(raw)
    if not v:
        return None, None

    if is_isbn13(v):
        isbn10 = isbn13_to_isbn10(v)
        return v, isbn10
    elif is_isbn10(v):
        isbn13 = isbn10_to_isbn13(v)
        return isbn13, v
    else:
        # Not a recognizable ISBN — store as-is in isbn field
        return raw.strip(), None


# ── Internal helpers ─────────────────────────────────────────────────────────


def _isbn13_check_digit(first_12: str) -> int:
    """Calculate the ISBN-13 check digit for the first 12 digits."""
    total = sum(int(ch) * (1 if i % 2 == 0 else 3) for i, ch in enumerate(first_12))
    remainder = total % 10
    return (10 - remainder) % 10


def _isbn10_check_digit(first_9: str) -> str:
    """Calculate the ISBN-10 check digit for the first 9 digits."""
    total = sum(int(ch) * (10 - i) for i, ch in enumerate(first_9))
    remainder = (11 - (total % 11)) % 11
    return "X" if remainder == 10 else str(remainder)
