"""Unit tests for the HTTP request handler utilities."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from src.adapters.authentication.exceptions import (
    AuthenticationError,
    AuthenticationGatewayError,
    AuthenticationServiceUnavailableError,
)
from src.adapters.authorization.exceptions import AuthorizationError
from src.domain.exceptions import ServiceError
from src.utils.http_request_handler import HttpRequestHandler


@pytest.fixture(autouse=True)
def mock_get_async_client():
    """Patch get_async_client so tests don't create real HTTP connections."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    with patch(
        "src.utils.http_request_handler.get_async_client", return_value=mock_client
    ) as _:
        yield mock_client


# ---------------------------------------------------------------------------
# Success path
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_post_success(mock_get_async_client):
    mock_response = httpx.Response(
        status_code=200,
        json={"result": "ok"},
        request=httpx.Request("POST", "http://auth/verify"),
    )
    mock_get_async_client.post = AsyncMock(return_value=mock_response)

    result = await HttpRequestHandler.post_with_error_handling(
        base_url="http://auth",
        path="/verify",
        json={"token": "abc"},
        headers={"X-Request-Id": "123"},
    )

    assert result == {"result": "ok"}
    mock_get_async_client.post.assert_awaited_once_with(
        "/verify", json={"token": "abc"}, headers={"X-Request-Id": "123"}
    )


# ---------------------------------------------------------------------------
# Status code error handling
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_post_401_raises_authentication_error(mock_get_async_client):
    mock_response = httpx.Response(
        status_code=401,
        json={"message": "Invalid token"},
        request=httpx.Request("POST", "http://auth/verify"),
    )
    mock_get_async_client.post = AsyncMock(return_value=mock_response)

    with pytest.raises(AuthenticationError, match="Invalid token"):
        await HttpRequestHandler.post_with_error_handling(
            base_url="http://auth", path="/verify"
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_post_401_with_no_body_uses_default_message(mock_get_async_client):
    mock_response = httpx.Response(
        status_code=401,
        text="",
        request=httpx.Request("POST", "http://auth/verify"),
    )
    mock_get_async_client.post = AsyncMock(return_value=mock_response)

    with pytest.raises(AuthenticationError, match="Unauthorized"):
        await HttpRequestHandler.post_with_error_handling(
            base_url="http://auth", path="/verify"
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_post_403_raises_authorization_error(mock_get_async_client):
    mock_response = httpx.Response(
        status_code=403,
        json={"error": "Access denied"},
        request=httpx.Request("POST", "http://auth/check"),
    )
    mock_get_async_client.post = AsyncMock(return_value=mock_response)

    with pytest.raises(AuthorizationError, match="Access denied"):
        await HttpRequestHandler.post_with_error_handling(
            base_url="http://auth", path="/check"
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_post_502_raises_gateway_error(mock_get_async_client):
    mock_response = httpx.Response(
        status_code=502,
        json={"detail": "upstream timeout"},
        request=httpx.Request("POST", "http://auth/verify"),
    )
    mock_get_async_client.post = AsyncMock(return_value=mock_response)

    with pytest.raises(AuthenticationGatewayError, match="Bad gateway"):
        await HttpRequestHandler.post_with_error_handling(
            base_url="http://auth", path="/verify"
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_post_503_raises_service_unavailable(mock_get_async_client):
    mock_response = httpx.Response(
        status_code=503,
        json={"description": "maintenance window"},
        request=httpx.Request("POST", "http://auth/verify"),
    )
    mock_get_async_client.post = AsyncMock(return_value=mock_response)

    with pytest.raises(AuthenticationServiceUnavailableError, match="temporarily"):
        await HttpRequestHandler.post_with_error_handling(
            base_url="http://auth", path="/verify"
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_post_500_raises_service_error(mock_get_async_client):
    mock_response = httpx.Response(
        status_code=500,
        text="Internal Server Error",
        request=httpx.Request("POST", "http://auth/verify"),
    )
    mock_get_async_client.post = AsyncMock(return_value=mock_response)

    with pytest.raises(ServiceError, match="Server error"):
        await HttpRequestHandler.post_with_error_handling(
            base_url="http://auth", path="/verify"
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_post_504_raises_service_error(mock_get_async_client):
    mock_response = httpx.Response(
        status_code=504,
        text="Gateway Timeout",
        request=httpx.Request("POST", "http://auth/verify"),
    )
    mock_get_async_client.post = AsyncMock(return_value=mock_response)

    with pytest.raises(ServiceError, match="Server error"):
        await HttpRequestHandler.post_with_error_handling(
            base_url="http://auth", path="/verify"
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_post_400_raises_service_error(mock_get_async_client):
    mock_response = httpx.Response(
        status_code=400,
        json={"message": "bad request"},
        request=httpx.Request("POST", "http://auth/verify"),
    )
    mock_get_async_client.post = AsyncMock(return_value=mock_response)

    with pytest.raises(ServiceError, match="Unexpected response status 400"):
        await HttpRequestHandler.post_with_error_handling(
            base_url="http://auth", path="/verify"
        )


# ---------------------------------------------------------------------------
# Network error handling
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_post_network_error_raises_service_unavailable(mock_get_async_client):
    request = httpx.Request("POST", "http://auth/verify")
    mock_get_async_client.post = AsyncMock(
        side_effect=httpx.ConnectError("Connection refused", request=request)
    )

    with pytest.raises(AuthenticationServiceUnavailableError, match="unreachable"):
        await HttpRequestHandler.post_with_error_handling(
            base_url="http://auth", path="/verify"
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_post_timeout_error_raises_service_unavailable(mock_get_async_client):
    request = httpx.Request("POST", "http://auth/verify")
    mock_get_async_client.post = AsyncMock(
        side_effect=httpx.ReadTimeout("Read timed out", request=request)
    )

    with pytest.raises(AuthenticationServiceUnavailableError, match="timed out"):
        await HttpRequestHandler.post_with_error_handling(
            base_url="http://auth", path="/verify"
        )


# ---------------------------------------------------------------------------
# JSON parse failure
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_post_invalid_json_response_raises_service_error(mock_get_async_client):
    mock_response = httpx.Response(
        status_code=200,
        text="not json at all",
        request=httpx.Request("POST", "http://auth/verify"),
        headers={"content-type": "text/plain"},
    )
    mock_get_async_client.post = AsyncMock(return_value=mock_response)

    with pytest.raises(ServiceError, match="Failed to parse response"):
        await HttpRequestHandler.post_with_error_handling(
            base_url="http://auth", path="/verify"
        )


# ---------------------------------------------------------------------------
# _extract_error_message tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_extract_error_message_from_message_field():
    response = httpx.Response(
        status_code=400,
        json={"message": "Something went wrong"},
        request=httpx.Request("POST", "http://x"),
    )
    result = HttpRequestHandler._extract_error_message(response)
    assert result == "Something went wrong"


@pytest.mark.unit
def test_extract_error_message_from_error_field():
    response = httpx.Response(
        status_code=400,
        json={"error": "Bad input"},
        request=httpx.Request("POST", "http://x"),
    )
    result = HttpRequestHandler._extract_error_message(response)
    assert result == "Bad input"


@pytest.mark.unit
def test_extract_error_message_from_single_key_dict():
    response = httpx.Response(
        status_code=400,
        json={"reason": "quota exceeded"},
        request=httpx.Request("POST", "http://x"),
    )
    result = HttpRequestHandler._extract_error_message(response)
    assert result == "quota exceeded"


@pytest.mark.unit
def test_extract_error_message_falls_back_to_text():
    response = httpx.Response(
        status_code=400,
        text="plain text error body",
        request=httpx.Request("POST", "http://x"),
        headers={"content-type": "text/plain"},
    )
    result = HttpRequestHandler._extract_error_message(response)
    assert result == "plain text error body"


@pytest.mark.unit
def test_extract_error_message_returns_none_for_empty():
    response = httpx.Response(
        status_code=400,
        text="",
        request=httpx.Request("POST", "http://x"),
    )
    result = HttpRequestHandler._extract_error_message(response)
    assert result is None
