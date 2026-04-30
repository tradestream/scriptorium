"""Open Graph metadata extractor — pulls structured data from web pages.

Extracts og:title, og:description, og:image, plus Dublin Core and
standard HTML meta tags as fallbacks. Useful for enriching book metadata
from publisher pages, Goodreads, Amazon, etc.
"""

import logging
import re

import httpx

logger = logging.getLogger("scriptorium.opengraph")

_META_PATTERN = re.compile(
    r'<meta\s+(?:[^>]*?\s)?'
    r'(?:property|name)\s*=\s*["\']([^"\']+)["\']'
    r'[^>]*?\s'
    r'content\s*=\s*["\']([^"\']*)["\']'
    r'[^>]*/?>',
    re.IGNORECASE | re.DOTALL,
)

_TITLE_PATTERN = re.compile(r'<title[^>]*>([^<]+)</title>', re.IGNORECASE)

# ISBN patterns in page text
_ISBN_PATTERN = re.compile(r'ISBN[-\s:]*(?:13[-\s:]*)?(?:978|979)[-\s]?\d[-\s]?\d{2,5}[-\s]?\d{2,7}[-\s]?\d', re.IGNORECASE)
_ISBN_CLEAN = re.compile(r'[\s-]')


async def extract_from_url(
    url: str,
    timeout: float = 15.0,
    *,
    max_bytes: int = 5 * 1024 * 1024,
) -> dict:
    """Fetch a URL and extract Open Graph / Dublin Core / HTML metadata.

    Refuses to fetch URLs that resolve to internal infrastructure
    (loopback, RFC1918, link-local cloud-metadata, etc.) — see
    ``app.utils.url_safety``. Caps the read size at ``max_bytes`` to
    keep a hostile / accidentally-huge page from spending all of our
    memory.

    Returns dict with:
        title, description, image_url, authors (list), isbn,
        publisher, language, published_date, source_url
    """
    from app.utils.url_safety import (
        UnsafeURLError,
        assert_safe_url,
        safe_redirect_chain,
    )

    result = {
        "title": None,
        "description": None,
        "image_url": None,
        "authors": [],
        "isbn": None,
        "publisher": None,
        "language": None,
        "published_date": None,
        "source_url": url,
    }

    try:
        assert_safe_url(url)
    except UnsafeURLError as exc:
        logger.warning("Refused to fetch %s: %s", url, exc)
        return result

    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": "Scriptorium/1.0 (book metadata)"},
            event_hooks={"response": [safe_redirect_chain()]},
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            # Cap response size — a hostile or buggy server could stream
            # gigabytes; we only ever look at the first few KB of HTML.
            html_bytes = resp.content[:max_bytes]
            html = html_bytes.decode(resp.encoding or "utf-8", errors="replace")
    except UnsafeURLError as exc:
        logger.warning("Refused redirect during fetch of %s: %s", url, exc)
        return result
    except Exception as exc:
        logger.warning("Failed to fetch %s: %s", url, exc)
        return result

    # Parse all meta tags
    meta = {}
    for match in _META_PATTERN.finditer(html):
        key = match.group(1).lower().strip()
        value = match.group(2).strip()
        if value:
            meta[key] = value

    # Title: og:title > dc.title > <title>
    result["title"] = (
        meta.get("og:title")
        or meta.get("dc.title")
        or meta.get("twitter:title")
    )
    if not result["title"]:
        m = _TITLE_PATTERN.search(html)
        if m:
            result["title"] = _unescape(m.group(1).strip())

    # Description: og:description > dc.description > meta description
    result["description"] = (
        meta.get("og:description")
        or meta.get("dc.description")
        or meta.get("twitter:description")
        or meta.get("description")
    )
    if result["description"]:
        result["description"] = _unescape(result["description"])

    # Image
    result["image_url"] = (
        meta.get("og:image")
        or meta.get("twitter:image")
        or meta.get("twitter:image:src")
    )
    # Make relative URLs absolute
    if result["image_url"] and result["image_url"].startswith("/"):
        from urllib.parse import urlparse
        parsed = urlparse(url)
        result["image_url"] = f"{parsed.scheme}://{parsed.netloc}{result['image_url']}"

    # Authors
    author = (
        meta.get("og:book:author")
        or meta.get("book:author")
        or meta.get("dc.creator")
        or meta.get("author")
    )
    if author:
        # Could be a URL (Goodreads) or a name
        if not author.startswith("http"):
            result["authors"] = [a.strip() for a in author.split(",") if a.strip()]

    # ISBN
    isbn = (
        meta.get("og:book:isbn")
        or meta.get("book:isbn")
        or meta.get("dc.identifier")
    )
    if isbn:
        clean = _ISBN_CLEAN.sub("", isbn)
        if re.match(r'^97[89]\d{10}$', clean):
            result["isbn"] = clean
        elif re.match(r'^\d{9}[\dXx]$', clean):
            result["isbn"] = clean

    # If no ISBN in meta, scan page text
    if not result["isbn"]:
        m = _ISBN_PATTERN.search(html)
        if m:
            clean = _ISBN_CLEAN.sub("", m.group(0).split(":")[-1].strip())
            if re.match(r'^97[89]\d{10}$', clean):
                result["isbn"] = clean

    # Publisher
    result["publisher"] = (
        meta.get("og:book:publisher")
        or meta.get("book:publisher")
        or meta.get("dc.publisher")
    )

    # Language
    lang = (
        meta.get("og:locale")
        or meta.get("dc.language")
        or meta.get("language")
    )
    if lang:
        # Normalize "en_US" -> "en"
        result["language"] = lang.split("_")[0].lower()

    # Published date
    result["published_date"] = (
        meta.get("og:book:release_date")
        or meta.get("book:release_date")
        or meta.get("dc.date")
        or meta.get("article:published_time")
        or meta.get("datePublished")
    )
    if result["published_date"]:
        result["published_date"] = result["published_date"][:10]

    # Clean up None/empty
    for key in list(result.keys()):
        if result[key] == "":
            result[key] = None

    return result


def _unescape(text: str) -> str:
    """Unescape basic HTML entities."""
    return (
        text.replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
        .replace("&#x27;", "'")
    )
