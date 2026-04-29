"""Coverage for ``assert_safe_url`` against the SSRF cases readest's review
flagged: IPv4 loopback, the unspecified address, RFC1918 ranges, AWS/GCP
metadata endpoint, IPv6 loopback / link-local / unique-local, bracketed
IPv6 forms, and bad-scheme refusal.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from app.utils.url_safety import (
    BodyTooLargeError,
    UnsafeURLError,
    assert_safe_url,
    fetch_capped,
)


class TestSchemeRejection:
    @pytest.mark.parametrize("url", [
        "file:///etc/passwd",
        "ftp://example.com/foo",
        "gopher://example.com/0",
        "javascript:alert(1)",
        "data:text/plain,hi",
    ])
    def test_non_http_schemes_rejected(self, url: str) -> None:
        with pytest.raises(UnsafeURLError):
            assert_safe_url(url)


class TestIPv4Literals:
    @pytest.mark.parametrize("url", [
        "http://127.0.0.1/x",
        "http://127.0.0.1:8080/foo",
        "http://0.0.0.0/x",
        "http://10.0.0.5/x",
        "http://172.16.0.1/x",
        "http://192.168.1.1/x",
        "http://169.254.169.254/latest/meta-data/",  # AWS / GCP metadata
        "http://224.0.0.1/x",                        # multicast
        "http://255.255.255.255/x",                  # broadcast (reserved)
    ])
    def test_internal_ipv4_rejected(self, url: str) -> None:
        with pytest.raises(UnsafeURLError):
            assert_safe_url(url)


class TestIPv6Literals:
    @pytest.mark.parametrize("url", [
        "http://[::1]/x",                # loopback
        "http://[::]/x",                 # unspecified
        "http://[fe80::1]/x",            # link-local
        "http://[fc00::1]/x",            # unique-local (private)
        "http://[fd00::1]/x",            # unique-local (private)
        "http://[ff02::1]/x",            # multicast
    ])
    def test_internal_ipv6_rejected(self, url: str) -> None:
        with pytest.raises(UnsafeURLError):
            assert_safe_url(url)


class TestReservedHostnames:
    @pytest.mark.parametrize("url", [
        "http://localhost/x",
        "http://localhost:8000/x",
        "http://LOCALHOST/x",
        "http://ip6-localhost/x",
        "http://ip6-loopback/x",
    ])
    def test_localhost_aliases_rejected(self, url: str) -> None:
        with pytest.raises(UnsafeURLError):
            assert_safe_url(url)


class TestMissingHost:
    @pytest.mark.parametrize("url", [
        "http://",
        "https:///path",
    ])
    def test_no_host_rejected(self, url: str) -> None:
        with pytest.raises(UnsafeURLError):
            assert_safe_url(url)


class TestDNSResolution:
    """A hostname that resolves to a private IP must be rejected — DNS
    rebinding tries to slip through with mixed answers, so *every*
    resolved address has to be public."""

    def test_dns_rebind_to_loopback_rejected(self) -> None:
        # ``getaddrinfo`` returns tuples of (family, type, proto, canon, sockaddr).
        # ``sockaddr[0]`` is the resolved IP string. We mock to simulate a
        # hostname that resolves to a private address.
        with patch(
            "app.utils.url_safety.socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("127.0.0.1", 0))],
        ):
            with pytest.raises(UnsafeURLError):
                assert_safe_url("http://attacker-controlled.example/x")

    def test_mixed_public_and_private_rejected(self) -> None:
        """If even one answer is internal, refuse — the resolver may pick
        the bad one on the actual fetch."""
        with patch(
            "app.utils.url_safety.socket.getaddrinfo",
            return_value=[
                (2, 1, 6, "", ("8.8.8.8", 0)),
                (2, 1, 6, "", ("10.0.0.5", 0)),
            ],
        ):
            with pytest.raises(UnsafeURLError):
                assert_safe_url("http://attacker-mixed.example/x")

    def test_public_only_accepted(self) -> None:
        with patch(
            "app.utils.url_safety.socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("8.8.8.8", 0))],
        ):
            assert_safe_url("http://public-only.example/x")  # no raise

    def test_unresolvable_rejected(self) -> None:
        import socket as _socket
        with patch(
            "app.utils.url_safety.socket.getaddrinfo",
            side_effect=_socket.gaierror("nope"),
        ):
            with pytest.raises(UnsafeURLError):
                assert_safe_url("http://nx.example/x")


class TestRedirectHook:
    """The hook re-validates the next-hop on every 3xx — a public origin
    that 302s to ``http://127.0.0.1`` must not be followed."""

    @pytest.mark.asyncio
    async def test_redirect_to_internal_ip_rejected(self) -> None:
        from unittest.mock import MagicMock
        from app.utils.url_safety import safe_redirect_chain

        hook = safe_redirect_chain()
        response = MagicMock()
        response.status_code = 302
        response.headers = {"location": "http://127.0.0.1/x"}
        with pytest.raises(UnsafeURLError):
            await hook(response)

    @pytest.mark.asyncio
    async def test_redirect_to_public_passes(self) -> None:
        from unittest.mock import MagicMock
        from app.utils.url_safety import safe_redirect_chain

        with patch(
            "app.utils.url_safety.socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("8.8.8.8", 0))],
        ):
            hook = safe_redirect_chain()
            response = MagicMock()
            response.status_code = 302
            response.headers = {"location": "http://public.example/next"}
            await hook(response)  # no raise

    @pytest.mark.asyncio
    async def test_non_redirect_response_skipped(self) -> None:
        from unittest.mock import MagicMock
        from app.utils.url_safety import safe_redirect_chain

        hook = safe_redirect_chain()
        response = MagicMock()
        response.status_code = 200
        response.headers = {}
        await hook(response)  # no raise even on a junk Location

    @pytest.mark.asyncio
    async def test_relative_redirect_resolved_against_request_url(self) -> None:
        """A ``Location: /image.jpg`` header is legal HTTP and must be
        resolved against the request URL rather than rejected for missing
        scheme/host."""
        from unittest.mock import MagicMock
        from app.utils.url_safety import safe_redirect_chain

        with patch(
            "app.utils.url_safety.socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("8.8.8.8", 0))],
        ):
            hook = safe_redirect_chain()
            response = MagicMock()
            response.status_code = 302
            response.headers = {"location": "/image.jpg"}
            response.request.url = "http://covers.example/list"
            await hook(response)  # no raise — resolves to public host

    @pytest.mark.asyncio
    async def test_relative_redirect_to_localhost_origin_rejected(self) -> None:
        """If the request itself was against localhost, a relative redirect
        still resolves there and must be rejected (defense-in-depth)."""
        from unittest.mock import MagicMock
        from app.utils.url_safety import safe_redirect_chain

        hook = safe_redirect_chain()
        response = MagicMock()
        response.status_code = 302
        response.headers = {"location": "/admin"}
        response.request.url = "http://127.0.0.1:8000/start"
        with pytest.raises(UnsafeURLError):
            await hook(response)


class TestFetchCapped:
    """Body-size enforcement on outbound fetches. A hostile origin can be
    inside our SSRF allowlist *and* still try to stream gigabytes."""

    @pytest.mark.asyncio
    async def test_content_length_over_cap_refused(self) -> None:
        from unittest.mock import AsyncMock, MagicMock

        client = MagicMock()
        response = MagicMock()
        response.headers = {"content-length": str(50 * 1024 * 1024)}
        response.status_code = 200
        response.aiter_bytes = MagicMock(return_value=AsyncMock())
        # ``stream`` is an async context manager
        client.stream = MagicMock()
        client.stream.return_value.__aenter__ = AsyncMock(return_value=response)
        client.stream.return_value.__aexit__ = AsyncMock(return_value=False)

        with pytest.raises(BodyTooLargeError):
            await fetch_capped(client, "http://example.com/x", max_bytes=10 * 1024 * 1024)

    @pytest.mark.asyncio
    async def test_streaming_over_cap_refused(self) -> None:
        """Server omits Content-Length and tries to stream past the cap."""
        from unittest.mock import AsyncMock, MagicMock

        # Build an async iterator that yields a 4 MB chunk, twice (8 MB total).
        chunk = b"x" * (4 * 1024 * 1024)
        async def aiter():
            yield chunk
            yield chunk

        response = MagicMock()
        response.headers = {}
        response.status_code = 200
        response.aiter_bytes = aiter

        client = MagicMock()
        client.stream = MagicMock()
        client.stream.return_value.__aenter__ = AsyncMock(return_value=response)
        client.stream.return_value.__aexit__ = AsyncMock(return_value=False)

        with pytest.raises(BodyTooLargeError):
            await fetch_capped(client, "http://example.com/x", max_bytes=5 * 1024 * 1024)

    @pytest.mark.asyncio
    async def test_under_cap_returns_full_body(self) -> None:
        from unittest.mock import AsyncMock, MagicMock

        async def aiter():
            yield b"hello"
            yield b" world"

        response = MagicMock()
        response.headers = {"content-type": "text/plain", "content-length": "11"}
        response.status_code = 200
        response.aiter_bytes = aiter

        client = MagicMock()
        client.stream = MagicMock()
        client.stream.return_value.__aenter__ = AsyncMock(return_value=response)
        client.stream.return_value.__aexit__ = AsyncMock(return_value=False)

        status_code, headers, body = await fetch_capped(
            client, "http://example.com/x", max_bytes=1024
        )
        assert status_code == 200
        assert body == b"hello world"
        assert headers["content-type"] == "text/plain"
