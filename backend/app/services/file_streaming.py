"""Shared HTTP file-serving helper with Range, ETag, and conditional requests.

FastAPI's bare ``FileResponse`` does not honor ``Range``, ``If-None-Match``,
or ``If-Range``. Kobo Nickel, Foliate, native readers, and audiobook clients
all rely on those — without them downloads can't resume, every page request
re-fetches whole chapters, and audiobook scrubbing breaks.

This module centralizes the server-side behavior so every file-serving
endpoint (book downloads, cover images, Kobo downloads, future audiobook
streaming) gets the same headers and the same partial-content handling.
"""
from __future__ import annotations

import hashlib
import os
import re
from datetime import datetime, timezone
from email.utils import format_datetime, parsedate_to_datetime
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, Request, Response, status
from fastapi.responses import FileResponse, StreamingResponse


CHUNK_SIZE = 64 * 1024  # 64 KiB — balanced for SMB-mounted NAS reads


def _format_http_date(ts: float) -> str:
    """Format a POSIX timestamp as an RFC 7231 IMF-fixdate string."""
    return format_datetime(datetime.fromtimestamp(ts, tz=timezone.utc), usegmt=True)


def _parse_http_date(value: str) -> Optional[datetime]:
    """Parse an RFC 7231 date header. Returns timezone-aware UTC or None."""
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _compute_etag(path: Path, stat_result: os.stat_result, salt: str = "") -> str:
    """Build a strong ETag from the file's identity + size + mtime.

    Strong (no ``W/`` prefix) so range requests against the same body match.
    The salt distinguishes the same on-disk path served under different
    semantic identities — e.g. a Kobo download URL keyed by edition UUID.
    """
    h = hashlib.sha1(usedforsecurity=False)
    h.update(str(path).encode("utf-8"))
    h.update(b"\0")
    h.update(str(stat_result.st_size).encode("ascii"))
    h.update(b"\0")
    h.update(str(int(stat_result.st_mtime)).encode("ascii"))
    if salt:
        h.update(b"\0")
        h.update(salt.encode("utf-8"))
    return f'"{h.hexdigest()}"'


_RANGE_RE = re.compile(r"^bytes=(\d*)-(\d*)$")


def _parse_range(header: str, file_size: int) -> Optional[tuple[int, int]]:
    """Parse a single-range ``Range: bytes=start-end`` header.

    Returns (start, end_inclusive) on success, or None if the header is
    malformed or out of range. Multi-range requests are not supported and
    return None — clients fall back to full responses, which is acceptable
    for our workloads (Kobo, Foliate, audiobook scrubbers all use single
    ranges).
    """
    match = _RANGE_RE.match(header.strip())
    if not match:
        return None
    start_s, end_s = match.group(1), match.group(2)
    if not start_s and not end_s:
        return None
    if not start_s:
        # Suffix range: "-N" means "last N bytes".
        suffix = int(end_s)
        if suffix <= 0:
            return None
        start = max(0, file_size - suffix)
        end = file_size - 1
    else:
        start = int(start_s)
        end = int(end_s) if end_s else file_size - 1
    if start >= file_size or start < 0 or end < start:
        return None
    end = min(end, file_size - 1)
    return start, end


async def _file_iterator(path: Path, start: int, length: int):
    """Yield bytes from ``path`` starting at ``start`` for ``length`` bytes."""
    remaining = length
    with path.open("rb") as f:
        f.seek(start)
        while remaining > 0:
            chunk = f.read(min(CHUNK_SIZE, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


def stream_file_response(
    request: Request,
    path: Path,
    *,
    media_type: str,
    filename: Optional[str] = None,
    cache_control: str = "private, max-age=0, must-revalidate",
    etag_salt: str = "",
) -> Response:
    """Serve a file with full Range/ETag/conditional-request support.

    Returns:
      - 304 Not Modified if If-None-Match or If-Modified-Since says the
        client already has a current copy.
      - 206 Partial Content with the requested byte range, when Range is
        present (and If-Range, if also present, matches).
      - 200 OK with the full file otherwise.

    Always emits ETag, Last-Modified, Accept-Ranges, and Cache-Control.
    """
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    stat = path.stat()
    file_size = stat.st_size
    etag = _compute_etag(path, stat, salt=etag_salt)
    last_modified = _format_http_date(stat.st_mtime)

    base_headers: dict[str, str] = {
        "ETag": etag,
        "Last-Modified": last_modified,
        "Accept-Ranges": "bytes",
        "Cache-Control": cache_control,
    }
    if filename:
        base_headers["Content-Disposition"] = f'attachment; filename="{filename}"'

    # Conditional request: 304 if the client's cached representation is
    # still current. ETag wins over Last-Modified (RFC 7232 §6).
    if_none_match = request.headers.get("if-none-match")
    if if_none_match:
        # Allow comma-separated lists, normalize whitespace.
        candidates = [t.strip() for t in if_none_match.split(",")]
        if etag in candidates or "*" in candidates:
            return Response(status_code=304, headers=base_headers)
    elif (ims := request.headers.get("if-modified-since")):
        client_dt = _parse_http_date(ims)
        if client_dt is not None:
            file_dt = datetime.fromtimestamp(int(stat.st_mtime), tz=timezone.utc)
            if file_dt <= client_dt:
                return Response(status_code=304, headers=base_headers)

    # Range request handling. If-Range guards the partial-content response:
    # if the validator the client holds doesn't match the current ETag /
    # mtime, fall back to a 200 with the whole file (per RFC 7233 §3.2).
    range_header = request.headers.get("range")
    if range_header:
        if_range = request.headers.get("if-range")
        range_valid = True
        if if_range:
            if if_range.strip().startswith('"') or if_range.strip().startswith("W/"):
                range_valid = if_range.strip() == etag
            else:
                ir_dt = _parse_http_date(if_range)
                file_dt = datetime.fromtimestamp(int(stat.st_mtime), tz=timezone.utc)
                range_valid = ir_dt is not None and ir_dt == file_dt

        if range_valid:
            parsed = _parse_range(range_header, file_size)
            if parsed is None:
                # 416 Range Not Satisfiable — include Content-Range so the
                # client knows the resource length.
                return Response(
                    status_code=416,
                    headers={**base_headers, "Content-Range": f"bytes */{file_size}"},
                )
            start, end = parsed
            length = end - start + 1
            partial_headers = {
                **base_headers,
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Content-Length": str(length),
                "Content-Type": media_type,
            }
            return StreamingResponse(
                _file_iterator(path, start, length),
                status_code=206,
                media_type=media_type,
                headers=partial_headers,
            )

    # Full-file response. FileResponse handles sendfile()/zero-copy on
    # Linux when the underlying transport allows it.
    return FileResponse(
        path=str(path),
        media_type=media_type,
        filename=filename,
        headers=base_headers,
    )
