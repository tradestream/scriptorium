"""KEPUB conversion service — converts EPUB to Kobo KEPUB format.

KEPUB is Kobo's enhanced EPUB format with:
- Kobo-specific span wrapping for precise reading position tracking
- Better page-turn performance
- Reading stats integration

Uses the `kepubify` CLI tool if available (https://pgaskin.net/kepubify/).
Falls back to a simple file copy with .kepub.epub extension if not installed.
"""

import asyncio
import hashlib
import logging
import os
import shutil
from pathlib import Path
from typing import Optional

from app.config import get_settings, resolve_path

logger = logging.getLogger(__name__)

_kepubify_path: Optional[str] = None
_kepubify_checked = False


def _find_kepubify() -> Optional[str]:
    """Find the kepubify binary on PATH."""
    global _kepubify_path, _kepubify_checked
    if _kepubify_checked:
        return _kepubify_path
    _kepubify_checked = True
    _kepubify_path = shutil.which("kepubify")
    if _kepubify_path:
        logger.info("Found kepubify at %s", _kepubify_path)
    else:
        logger.info("kepubify not found — KEPUB conversion will use simple rename")
    return _kepubify_path


def _safe_kepub_name(source: Path) -> str:
    """Generate a KEPUB filename safe for ext4's 255-byte limit.

    kepubify creates temp files like `.kepubify.{name}_converted.kepub.epub.{random}`
    which adds ~40 chars of overhead. Anna's Archive filenames can be 230+ chars,
    blowing past the limit. Truncate the stem to 200 chars to stay safe.
    """
    stem = source.stem
    if len(stem.encode("utf-8")) > 200:
        # Truncate to 200 bytes, respecting UTF-8 boundaries
        encoded = stem.encode("utf-8")[:200]
        stem = encoded.decode("utf-8", errors="ignore").rstrip()
        logger.info("Truncated long filename for kepubify: %s... (%d bytes)", stem[:50], len(encoded))
    return stem + ".kepub.epub"


async def convert_to_kepub(epub_path: str) -> Optional[str]:
    """Convert an EPUB file to KEPUB format.

    Returns the path to the generated .kepub.epub file, or None on failure.
    """
    resolved = resolve_path(epub_path)
    source = Path(resolved)
    if not source.exists():
        logger.warning("EPUB not found for KEPUB conversion: %s", resolved)
        return None

    # Output directory: prefer next to source, fall back to cache dir
    # (library mounts may be read-only)
    kepub_name = _safe_kepub_name(source)
    output_dir = source.parent
    kepub_path = output_dir / kepub_name

    # Check if source dir is writable; if not, use cache dir
    if not os.access(str(output_dir), os.W_OK):
        settings = get_settings()
        cache_dir = Path(settings.COVERS_PATH).parent / "kepub_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        output_dir = cache_dir
        kepub_path = output_dir / kepub_name
        logger.debug("Library dir not writable, using cache: %s", output_dir)

    # If already converted, return existing
    if kepub_path.exists():
        return str(kepub_path)

    kepubify = _find_kepubify()
    if kepubify:
        try:
            proc = await asyncio.create_subprocess_exec(
                kepubify, str(source), "-o", str(output_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode == 0 and kepub_path.exists():
                logger.info("Converted to KEPUB: %s", kepub_name)
                return str(kepub_path)
            else:
                logger.warning("kepubify failed (rc=%d): %s", proc.returncode, stderr.decode()[:200])
        except Exception as exc:
            logger.warning("kepubify error: %s", exc)

    # Fallback: copy with .kepub.epub extension (Kobo accepts it, just no span wrapping)
    try:
        shutil.copy2(str(source), str(kepub_path))
        logger.info("Copied EPUB as KEPUB (no kepubify): %s", kepub_name)
        return str(kepub_path)
    except Exception as exc:
        logger.warning("KEPUB copy failed: %s", exc)
        return None


def hash_file(path: str) -> str:
    """SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


async def ensure_kepub(edition_file, *, is_fixed_layout: bool = False) -> Optional[str]:
    """Ensure a KEPUB version exists for an EditionFile.

    Returns the kepub_path if successful, or None. Returns None for fixed-
    layout EPUBs — KEPUB conversion mangles pre-paginated content (the
    container reflows everything as a single ePub3 chapter), so we serve
    the original .epub for those titles. Kobo Nickel handles fixed-layout
    EPUB3 natively when advertised under the EPUB3FL format.

    Caches the result on the EditionFile model (kepub_path, kepub_hash).
    """
    if edition_file.format.lower() not in ("epub",):
        return None  # Only convert EPUBs

    if is_fixed_layout:
        return None

    # Already have a cached KEPUB?
    if edition_file.kepub_path:
        resolved = resolve_path(edition_file.kepub_path)
        if Path(resolved).exists():
            return edition_file.kepub_path

    # Convert
    kepub_path = await convert_to_kepub(edition_file.file_path)
    if kepub_path:
        edition_file.kepub_path = kepub_path
        edition_file.kepub_hash = hash_file(resolve_path(kepub_path))
        # Extract per-chapter koboSpan ids so we can round-trip Kobo Nickel
        # bookmarks against real positions instead of synthetic spine#N
        # tokens. Failure is non-fatal — sync still works without spans, it
        # just falls back to spine-level resolution.
        try:
            from sqlalchemy.ext.asyncio import async_object_session
            from app.services.kobo_spans import extract_span_maps, store_span_maps

            async_session = async_object_session(edition_file)
            if async_session is not None:
                maps = extract_span_maps(Path(resolve_path(kepub_path)))
                if maps:
                    await store_span_maps(edition_file.id, maps, async_session)
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning("Failed to extract KoboSpan map for %s: %s", kepub_path, exc)
        return kepub_path

    return None
