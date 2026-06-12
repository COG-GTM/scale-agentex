"""Unit tests for the httpx HTTP adapter.

Tests cover async_call, call, stream_call, client lifecycle, and error handling.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from httpx import ConnectError, HTTPStatusError, Request, Response, TimeoutException
from src.adapters.http.adapter_httpx import HttpxGateway


@pytest.fixture(autouse=True)
def reset_httpx_gateway_class_state():
    """Reset class-level cached clients between tests."""
    HttpxGateway._regular_client = None
    HttpxGateway._streaming_client = None
    HttpxGateway._environment_variables = None
    yield
    HttpxGateway._regular_client = None
    HttpxGateway._streaming_client = None
    HttpxGateway._environment_variables = None


def _make_env_vars() -> MagicMock:
    env = MagicMock()
    env.HTTPX_MAX_CONNECTIONS = 200
    env.HTTPX_MAX_KEEPALIVE_CONNECTIONS = 100
    env.HTTPX_CONNECT_TIMEOUT = 10.0
    env.HTTPX_READ_TIMEOUT = 30.0
    env.HTTPX_WRITE_TIMEOUT = 30.0
    env.HTTPX_POOL_TIMEOUT = 10.0
    env.HTTPX_STREAMING_READ_TIMEOUT = 300.0
    return env


# ---------------------------------------------------------------------------
# async_call tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_async_call_get_success():
    env = _make_env_vars()
    gateway = HttpxGateway(env)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"key": "value"}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.request = AsyncMock(return_value=mock_response)

    with patch.object(HttpxGateway, "_get_regular_client", return_value=mock_client):
        result = await gateway.async_call("GET", "https://example.com/api")

    assert result == {"key": "value"}
    mock_client.request.assert_awaited_once()
    call_kwargs = mock_client.request.call_args[1]
    assert call_kwargs["method"] == "GET"
    assert call_kwargs["url"] == "https://example.com/api"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_async_call_post_with_payload():
    env = _make_env_vars()
    gateway = HttpxGateway(env)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"created": True}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.request = AsyncMock(return_value=mock_response)

    with patch.object(HttpxGateway, "_get_regular_client", return_value=mock_client):
        result = await gateway.async_call(
            "POST",
            "https://example.com/api",
            payload={"name": "test"},
            default_headers={"X-Custom": "header"},
        )

    assert result == {"created": True}
    call_kwargs = mock_client.request.call_args[1]
    assert call_kwargs["json"] == {"name": "test"}
    assert call_kwargs["headers"] == {"X-Custom": "header"}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_async_call_with_custom_timeout():
    env = _make_env_vars()
    gateway = HttpxGateway(env)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.request = AsyncMock(return_value=mock_response)

    with patch.object(HttpxGateway, "_get_regular_client", return_value=mock_client):
        await gateway.async_call("GET", "https://example.com/api", timeout=60)

    call_kwargs = mock_client.request.call_args[1]
    assert call_kwargs["timeout"] == 60.0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_async_call_raises_http_status_error():
    env = _make_env_vars()
    gateway = HttpxGateway(env)

    request = Request("GET", "https://example.com/api")
    response = Response(status_code=404, request=request)
    error = HTTPStatusError("Not Found", request=request, response=response)

    mock_client = AsyncMock()
    mock_client.request = AsyncMock(side_effect=error)

    with patch.object(HttpxGateway, "_get_regular_client", return_value=mock_client):
        with pytest.raises(HTTPStatusError):
            await gateway.async_call("GET", "https://example.com/api")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_async_call_raises_connect_error():
    env = _make_env_vars()
    gateway = HttpxGateway(env)

    mock_client = AsyncMock()
    mock_client.request = AsyncMock(side_effect=ConnectError("Connection refused"))

    with patch.object(HttpxGateway, "_get_regular_client", return_value=mock_client):
        with pytest.raises(ConnectError):
            await gateway.async_call("GET", "https://example.com/api")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_async_call_raises_timeout_exception():
    env = _make_env_vars()
    gateway = HttpxGateway(env)

    mock_client = AsyncMock()
    mock_client.request = AsyncMock(side_effect=TimeoutException("Read timed out"))

    with patch.object(HttpxGateway, "_get_regular_client", return_value=mock_client):
        with pytest.raises(TimeoutException):
            await gateway.async_call("GET", "https://example.com/api")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_async_call_raises_unexpected_error():
    env = _make_env_vars()
    gateway = HttpxGateway(env)

    mock_client = AsyncMock()
    mock_client.request = AsyncMock(side_effect=RuntimeError("unexpected"))

    with patch.object(HttpxGateway, "_get_regular_client", return_value=mock_client):
        with pytest.raises(RuntimeError):
            await gateway.async_call("GET", "https://example.com/api")


# ---------------------------------------------------------------------------
# call (sync) tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_sync_call_get_success():
    env = _make_env_vars()
    gateway = HttpxGateway(env)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"sync": True}
    mock_response.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.request.return_value = mock_response
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)

    with patch(
        "src.adapters.http.adapter_httpx.httpx.Client", return_value=mock_client
    ):
        result = gateway.call("GET", "https://example.com/api")

    assert result == {"sync": True}


@pytest.mark.unit
def test_sync_call_with_custom_timeout():
    env = _make_env_vars()
    gateway = HttpxGateway(env)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {}
    mock_response.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.request.return_value = mock_response
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)

    with patch(
        "src.adapters.http.adapter_httpx.httpx.Client", return_value=mock_client
    ) as mock_cls:
        gateway.call("GET", "https://example.com/api", timeout=120)

    # Verify custom timeout was used
    call_kwargs = mock_cls.call_args[1]
    assert call_kwargs["timeout"].connect == 120.0


@pytest.mark.unit
def test_sync_call_raises_http_status_error():
    env = _make_env_vars()
    gateway = HttpxGateway(env)

    request = Request("POST", "https://example.com/api")
    response = Response(status_code=500, request=request)
    error = HTTPStatusError("Server Error", request=request, response=response)

    mock_client = MagicMock()
    mock_client.request.side_effect = error
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)

    with patch(
        "src.adapters.http.adapter_httpx.httpx.Client", return_value=mock_client
    ):
        with pytest.raises(HTTPStatusError):
            gateway.call("POST", "https://example.com/api", payload={"x": 1})


@pytest.mark.unit
def test_sync_call_raises_connect_error():
    env = _make_env_vars()
    gateway = HttpxGateway(env)

    mock_client = MagicMock()
    mock_client.request.side_effect = ConnectError("Connection refused")
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)

    with patch(
        "src.adapters.http.adapter_httpx.httpx.Client", return_value=mock_client
    ):
        with pytest.raises(ConnectError):
            gateway.call("GET", "https://example.com/api")


@pytest.mark.unit
def test_sync_call_raises_timeout_exception():
    env = _make_env_vars()
    gateway = HttpxGateway(env)

    mock_client = MagicMock()
    mock_client.request.side_effect = TimeoutException("timed out")
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)

    with patch(
        "src.adapters.http.adapter_httpx.httpx.Client", return_value=mock_client
    ):
        with pytest.raises(TimeoutException):
            gateway.call("GET", "https://example.com/api")


# ---------------------------------------------------------------------------
# stream_call tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_stream_call_yields_json_lines():
    env = _make_env_vars()
    gateway = HttpxGateway(env)

    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()

    async def mock_aiter_lines():
        yield '{"chunk": 1}'
        yield '{"chunk": 2}'
        yield ""  # empty line should be skipped
        yield '{"chunk": 3}'

    mock_response.aiter_lines = mock_aiter_lines
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=False)

    mock_client = MagicMock()
    mock_client.stream = MagicMock(return_value=mock_response)

    with patch.object(HttpxGateway, "_get_streaming_client", return_value=mock_client):
        results = []
        async for item in gateway.stream_call("POST", "https://example.com/stream"):
            results.append(item)

    assert results == [{"chunk": 1}, {"chunk": 2}, {"chunk": 3}]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_stream_call_skips_invalid_json():
    env = _make_env_vars()
    gateway = HttpxGateway(env)

    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()

    async def mock_aiter_lines():
        yield '{"valid": true}'
        yield "not valid json"
        yield '{"also_valid": true}'

    mock_response.aiter_lines = mock_aiter_lines
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=False)

    mock_client = MagicMock()
    mock_client.stream = MagicMock(return_value=mock_response)

    with patch.object(HttpxGateway, "_get_streaming_client", return_value=mock_client):
        results = []
        async for item in gateway.stream_call("POST", "https://example.com/stream"):
            results.append(item)

    assert results == [{"valid": True}, {"also_valid": True}]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_stream_call_sets_sse_headers():
    env = _make_env_vars()
    gateway = HttpxGateway(env)

    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()

    async def mock_aiter_lines():
        return
        yield  # pragma: no cover

    mock_response.aiter_lines = mock_aiter_lines
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=False)

    mock_client = MagicMock()
    mock_client.stream = MagicMock(return_value=mock_response)

    with patch.object(HttpxGateway, "_get_streaming_client", return_value=mock_client):
        async for _ in gateway.stream_call("POST", "https://example.com/stream"):
            pass  # pragma: no cover

    call_kwargs = mock_client.stream.call_args[1]
    assert call_kwargs["headers"]["Accept"] == "text/event-stream"
    assert call_kwargs["headers"]["Content-Type"] == "application/json"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_stream_call_raises_http_status_error():
    env = _make_env_vars()
    gateway = HttpxGateway(env)

    request = Request("POST", "https://example.com/stream")
    response = Response(status_code=503, request=request)
    error = HTTPStatusError("Service Unavailable", request=request, response=response)

    mock_response = AsyncMock()
    mock_response.raise_for_status = MagicMock(side_effect=error)
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=False)

    mock_client = MagicMock()
    mock_client.stream = MagicMock(return_value=mock_response)

    with patch.object(HttpxGateway, "_get_streaming_client", return_value=mock_client):
        with pytest.raises(HTTPStatusError):
            async for _ in gateway.stream_call("POST", "https://example.com/stream"):
                pass  # pragma: no cover


# ---------------------------------------------------------------------------
# Client lifecycle tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_get_regular_client_creates_client():
    env = _make_env_vars()
    HttpxGateway(env)

    client = HttpxGateway._get_regular_client()
    assert isinstance(client, httpx.AsyncClient)


@pytest.mark.unit
def test_get_regular_client_is_cached():
    env = _make_env_vars()
    HttpxGateway(env)

    client1 = HttpxGateway._get_regular_client()
    client2 = HttpxGateway._get_regular_client()
    assert client1 is client2


@pytest.mark.unit
def test_get_streaming_client_creates_client():
    env = _make_env_vars()
    HttpxGateway(env)

    client = HttpxGateway._get_streaming_client()
    assert isinstance(client, httpx.AsyncClient)


@pytest.mark.unit
def test_get_streaming_client_is_cached():
    env = _make_env_vars()
    HttpxGateway(env)

    client1 = HttpxGateway._get_streaming_client()
    client2 = HttpxGateway._get_streaming_client()
    assert client1 is client2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_close_clients():
    env = _make_env_vars()
    HttpxGateway(env)

    # Create both clients
    HttpxGateway._get_regular_client()
    HttpxGateway._get_streaming_client()

    assert HttpxGateway._regular_client is not None
    assert HttpxGateway._streaming_client is not None

    await HttpxGateway.close_clients()

    assert HttpxGateway._regular_client is None
    assert HttpxGateway._streaming_client is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_close_clients_when_none():
    """close_clients should not raise when no clients exist."""
    await HttpxGateway.close_clients()


@pytest.mark.unit
def test_init_sets_environment_variables_only_once():
    env1 = _make_env_vars()
    env2 = _make_env_vars()

    HttpxGateway(env1)
    HttpxGateway(env2)

    # First env should stick
    assert HttpxGateway._environment_variables is env1
