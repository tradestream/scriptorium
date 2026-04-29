"""Public base-URL resolution for client-facing links.

Three callers (Kobo sync init, OPDS feed, DiViNa manifest) generate
absolute URLs into the response body that the client then re-uses.
Trusting ``X-Forwarded-Host`` / ``X-Forwarded-Proto`` unconditionally
lets any client poison those URLs by sending a forged header — covers
get fetched from attacker-controlled hosts, Kobo sync points at the
wrong server, etc.

Resolution order:

  1. ``PUBLIC_BASE_URL`` — pinned config, most explicit. Use this in
     production deployments behind any kind of proxy.
  2. ``X-Forwarded-{Proto,Host}`` — only when ``TRUST_FORWARDED_HEADERS``
     is on. The deployer is opting in: "my reverse proxy is trusted to
     overwrite these on every request, no untrusted client is able to
     reach the app directly."
  3. Otherwise, the request's own scheme + host — what the ASGI server
     actually saw.
"""
from __future__ import annotations

from fastapi import Request

from app.config import get_settings


def public_base_url(request: Request) -> str:
    """Return the canonical ``scheme://host`` for client-facing links.

    No trailing slash. Callers append ``/api/...`` etc. directly.
    """
    settings = get_settings()
    if settings.PUBLIC_BASE_URL:
        return settings.PUBLIC_BASE_URL.rstrip("/")
    if settings.TRUST_FORWARDED_HEADERS:
        scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
        host = request.headers.get("x-forwarded-host", request.url.netloc)
        return f"{scheme}://{host}"
    return f"{request.url.scheme}://{request.url.netloc}"
