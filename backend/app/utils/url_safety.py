"""Validate user-supplied URLs before the server fetches them.

Used by every code path that takes a URL from a request body and turns
around to issue an outbound HTTP fetch (open-graph metadata extraction,
cover-image enrichment, etc.). Without this, an authenticated user can
make the server probe internal services (``127.0.0.1``, RFC1918, link-
local cloud metadata at ``169.254.169.254``, the docker bridge network,
etc.) — classic SSRF.

The validator runs once before the initial fetch *and* again on every
redirect, since a redirect target can be different from the URL the
caller submitted.
"""
from __future__ import annotations

import ipaddress
import socket
from typing import Iterable
from urllib.parse import urlparse


_ALLOWED_SCHEMES: frozenset[str] = frozenset({"http", "https"})


class UnsafeURLError(ValueError):
    """Raised when a URL fails the safety check."""


def _is_private_address(addr: str) -> bool:
    """True if ``addr`` is a private / loopback / link-local / multicast IP."""
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return False
    return (
        ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def assert_safe_url(url: str) -> None:
    """Reject any URL that could reach internal infrastructure.

    Raises ``UnsafeURLError`` for: non-http(s) schemes, missing host,
    hostnames that resolve to loopback/private/link-local/multicast
    IPs (checking *every* resolved address — DNS rebinding tries to
    sneak through with mixed answers), and reserved literals like
    ``localhost`` or ``[::1]``.
    """
    parsed = urlparse(url.strip())
    scheme = (parsed.scheme or "").lower()
    if scheme not in _ALLOWED_SCHEMES:
        raise UnsafeURLError(f"only http/https URLs are accepted (got {scheme!r})")
    host = (parsed.hostname or "").strip().lower()
    if not host:
        raise UnsafeURLError("URL has no host component")
    if host in {"localhost", "ip6-localhost", "ip6-loopback", "::1"}:
        raise UnsafeURLError(f"refusing to fetch from {host!r}")

    # If the host is an IP literal, check it directly.
    try:
        ip = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        ip = None
    if ip is not None and _is_private_address(str(ip)):
        raise UnsafeURLError(f"refusing to fetch from private/internal IP {host!r}")

    # Otherwise resolve via DNS and reject if *any* answer is internal.
    if ip is None:
        try:
            infos = socket.getaddrinfo(host, None)
        except socket.gaierror as exc:
            raise UnsafeURLError(f"DNS resolution failed: {exc}") from exc
        seen: set[str] = set()
        for info in infos:
            sockaddr = info[4]
            addr = sockaddr[0]
            if addr in seen:
                continue
            seen.add(addr)
            if _is_private_address(addr):
                raise UnsafeURLError(
                    f"hostname {host!r} resolves to private/internal IP {addr!r}"
                )
        if not seen:
            raise UnsafeURLError(f"hostname {host!r} did not resolve")


def safe_redirect_chain(allowed_schemes: Iterable[str] = ("http", "https")):
    """Return an httpx event hook that re-validates each redirect target.

    Use as ``async with httpx.AsyncClient(event_hooks={'response':
    [safe_redirect_chain()]}) as client``. Every 3xx response triggers
    a fresh ``assert_safe_url`` call against the next-hop URL before
    httpx follows it.

    Resolves relative ``Location`` values (e.g. ``/image.jpg``) against
    the response's request URL before validation — otherwise legitimate
    same-origin redirects get rejected for "no scheme/host".
    """
    from urllib.parse import urljoin

    async def hook(response):
        if 300 <= response.status_code < 400:
            location = response.headers.get("location")
            if location:
                next_url = urljoin(str(response.request.url), location)
                assert_safe_url(next_url)
    return hook


# Default body cap for outbound metadata fetches: large enough for any
# reasonable cover image, small enough to refuse a hostile origin
# streaming gigabytes into our process memory.
DEFAULT_MAX_BODY_BYTES = 20 * 1024 * 1024  # 20 MiB


class BodyTooLargeError(Exception):
    """Raised when an outbound fetch's response body exceeds the cap.

    Intentionally not a ``ValueError`` subclass — the streaming reader
    has a ``try / except ValueError`` around its integer parse, and we
    don't want our own raise getting swallowed by it.
    """


async def fetch_capped(
    client,
    url: str,
    *,
    max_bytes: int = DEFAULT_MAX_BODY_BYTES,
    method: str = "GET",
    **kwargs,
) -> tuple[int, dict, bytes]:
    """Issue an outbound request and return (status, headers, body) with
    the body capped at ``max_bytes``.

    Two enforcement layers:

      1. ``Content-Length``: if the server advertises a length larger than
         the cap, refuse before reading the body.
      2. Streaming: read in chunks, accumulate bytes, raise once the cap
         is exceeded so a server lying about (or omitting)
         ``Content-Length`` can't pin gigabytes in memory.

    Caller is responsible for the ``httpx.AsyncClient`` (so they own the
    timeout / event-hooks / pool config). Returns headers as a plain
    dict so callers don't depend on httpx-specific types.
    """
    async with client.stream(method, url, **kwargs) as response:
        advertised = response.headers.get("content-length")
        if advertised:
            try:
                if int(advertised) > max_bytes:
                    raise BodyTooLargeError(
                        f"Content-Length {advertised} exceeds cap {max_bytes}"
                    )
            except ValueError:
                # Non-numeric Content-Length is a server bug; fall through
                # to the streaming check rather than refuse outright.
                pass
        chunks: list[bytes] = []
        total = 0
        async for chunk in response.aiter_bytes():
            total += len(chunk)
            if total > max_bytes:
                raise BodyTooLargeError(
                    f"response body exceeded cap {max_bytes} bytes"
                )
            chunks.append(chunk)
        return response.status_code, dict(response.headers), b"".join(chunks)
