"""Unit tests for URL validation (SSRF guard)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from src.domain.exceptions import ClientError
from src.utils.url_validation import validate_external_url


@pytest.mark.unit
@pytest.mark.asyncio
async def test_rejects_http_scheme():
    with pytest.raises(ClientError, match="scheme must be 'https'"):
        await validate_external_url("http://example.com/path")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_rejects_ftp_scheme():
    with pytest.raises(ClientError, match="scheme must be 'https'"):
        await validate_external_url("ftp://example.com/path")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_rejects_empty_scheme():
    with pytest.raises(ClientError, match="scheme must be 'https'"):
        await validate_external_url("://example.com/path")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_rejects_missing_hostname():
    with pytest.raises(ClientError, match="must include a hostname"):
        await validate_external_url("https:///path/only")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_rejects_private_ip():
    """DNS resolving to 192.168.x.x should be rejected."""
    fake_infos = [
        (2, 1, 6, "", ("192.168.1.1", 443)),
    ]
    with patch("asyncio.get_event_loop") as mock_loop:
        mock_loop.return_value.getaddrinfo = _async_return(fake_infos)
        with pytest.raises(ClientError, match="non-public address"):
            await validate_external_url("https://internal.example.com/path")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_rejects_loopback_ip():
    """DNS resolving to 127.0.0.1 should be rejected."""
    fake_infos = [
        (2, 1, 6, "", ("127.0.0.1", 443)),
    ]
    with patch("asyncio.get_event_loop") as mock_loop:
        mock_loop.return_value.getaddrinfo = _async_return(fake_infos)
        with pytest.raises(ClientError, match="non-public address"):
            await validate_external_url("https://localhost/path")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_rejects_link_local_ip():
    """DNS resolving to 169.254.x.x should be rejected."""
    fake_infos = [
        (2, 1, 6, "", ("169.254.169.254", 80)),
    ]
    with patch("asyncio.get_event_loop") as mock_loop:
        mock_loop.return_value.getaddrinfo = _async_return(fake_infos)
        with pytest.raises(ClientError, match="non-public address"):
            await validate_external_url("https://metadata.internal/path")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_rejects_ipv6_loopback():
    """DNS resolving to ::1 should be rejected."""
    fake_infos = [
        (10, 1, 6, "", ("::1", 443, 0, 0)),
    ]
    with patch("asyncio.get_event_loop") as mock_loop:
        mock_loop.return_value.getaddrinfo = _async_return(fake_infos)
        with pytest.raises(ClientError, match="non-public address"):
            await validate_external_url("https://ipv6loopback.test/path")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_accepts_public_ip():
    """DNS resolving to a public IP should pass."""
    fake_infos = [
        (2, 1, 6, "", ("93.184.216.34", 443)),
    ]
    with patch("asyncio.get_event_loop") as mock_loop:
        mock_loop.return_value.getaddrinfo = _async_return(fake_infos)
        # Should not raise
        await validate_external_url("https://example.com/path")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_accepts_multiple_public_ips():
    """All resolved IPs must be public."""
    fake_infos = [
        (2, 1, 6, "", ("93.184.216.34", 443)),
        (2, 1, 6, "", ("93.184.216.35", 443)),
    ]
    with patch("asyncio.get_event_loop") as mock_loop:
        mock_loop.return_value.getaddrinfo = _async_return(fake_infos)
        await validate_external_url("https://example.com/path")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_rejects_if_any_ip_is_private():
    """If any resolved IP is private, reject."""
    fake_infos = [
        (2, 1, 6, "", ("93.184.216.34", 443)),
        (2, 1, 6, "", ("10.0.0.1", 443)),
    ]
    with patch("asyncio.get_event_loop") as mock_loop:
        mock_loop.return_value.getaddrinfo = _async_return(fake_infos)
        with pytest.raises(ClientError, match="non-public address"):
            await validate_external_url("https://sneaky.example.com/path")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_raises_on_dns_resolution_failure():
    """OSError during DNS resolution should surface as ClientError."""
    with patch("asyncio.get_event_loop") as mock_loop:
        mock_loop.return_value.getaddrinfo = _async_raise(
            OSError("Name or service not known")
        )
        with pytest.raises(ClientError, match="Could not resolve hostname"):
            await validate_external_url("https://nonexistent.invalid/path")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_uses_port_from_url():
    """Port from URL should be used for resolution."""
    fake_infos = [
        (2, 1, 6, "", ("93.184.216.34", 8443)),
    ]
    mock_getaddrinfo = AsyncMock(return_value=fake_infos)
    with patch("asyncio.get_event_loop") as mock_loop:
        mock_loop.return_value.getaddrinfo = mock_getaddrinfo
        await validate_external_url("https://example.com:8443/path")
        mock_getaddrinfo.assert_awaited_once_with("example.com", 8443)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _async_return(value):
    """Create an async function that returns a value."""

    async def _fn(*args, **kwargs):
        return value

    return _fn


def _async_raise(exc):
    """Create an async function that raises an exception."""

    async def _fn(*args, **kwargs):
        raise exc

    return _fn
