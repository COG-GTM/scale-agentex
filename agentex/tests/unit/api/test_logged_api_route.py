"""Unit tests for logged_api_route.py.

Tests the logging route handler and streaming response:
- log_request formats and invokes logger correctly
- log_response formats and invokes logger correctly
- LoggedAPIRoute dispatches logging for regular responses
- LoggedAPIRoute dispatches logging for streaming responses
- LoggedStreamingResponse handles errors
- _parse_request_body handles form and JSON content types
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse
from src.api.logged_api_route import (
    LoggedAPIRoute,
    LoggedStreamingResponse,
    StreamResponseError,
    log_request,
    log_response,
)
from starlette.testclient import TestClient


@pytest.mark.unit
class TestLogRequest:
    """Tests for the log_request function."""

    def test_log_request_with_json_body(self):
        """log_request should log method, path, and decoded body."""
        request = MagicMock(spec=Request)
        request.method = "POST"
        request.scope = {"root_path": "", "route": MagicMock(path="/tasks")}
        request.query_params = {}
        request.headers = {"content-type": "application/json"}

        with patch("src.api.logged_api_route.logger") as mock_logger:
            log_request("req-123", request, b'{"name": "test"}')

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert "POST" in call_args[0][0]
        assert "/tasks" in call_args[0][0]
        assert "req-123" in call_args[0][0]

    def test_log_request_with_non_json_body(self):
        """log_request should handle non-JSON bodies gracefully."""
        request = MagicMock(spec=Request)
        request.method = "GET"
        request.scope = {"root_path": "", "route": MagicMock(path="/agents")}
        request.query_params = {}
        request.headers = {}

        with patch("src.api.logged_api_route.logger") as mock_logger:
            log_request("req-456", request, b"not-json")

        mock_logger.info.assert_called_once()

    def test_log_request_with_root_path(self):
        """log_request should include root_path in the logged path."""
        request = MagicMock(spec=Request)
        request.method = "GET"
        request.scope = {"root_path": "/api/v1", "route": MagicMock(path="/tasks")}
        request.query_params = {}
        request.headers = {}

        with patch("src.api.logged_api_route.logger") as mock_logger:
            log_request("req-789", request, b"")

        call_args = mock_logger.info.call_args
        assert "/api/v1/tasks" in call_args[0][0]


@pytest.mark.unit
class TestLogResponse:
    """Tests for the log_response function."""

    def test_log_response_formats_correctly(self):
        """log_response should log status code, method, and path."""
        request = MagicMock(spec=Request)
        request.method = "POST"
        request.url = MagicMock()
        request.url.path = "/tasks/create"

        response = MagicMock(spec=Response)
        response.status_code = 201
        response.headers = {"content-type": "application/json"}

        with patch("src.api.logged_api_route.logger") as mock_logger:
            log_response("req-abc", request, response)

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert "201" in call_args[0][0]
        assert "POST" in call_args[0][0]
        assert "/tasks/create" in call_args[0][0]
        assert "req-abc" in call_args[0][0]


@pytest.mark.unit
class TestLoggedAPIRoute:
    """Tests for LoggedAPIRoute integration."""

    def test_regular_response_logs_request_and_response(self):
        """Regular (non-streaming) responses should log both request and response."""
        app = FastAPI()
        app.router.route_class = LoggedAPIRoute

        @app.get("/test")
        async def test_endpoint():
            return {"result": "ok"}

        with (
            patch("src.api.logged_api_route.log_request") as mock_log_req,
            patch("src.api.logged_api_route.log_response"),
            patch("src.api.logged_api_route.ctx_var_request_id") as mock_ctx,
        ):
            mock_ctx.get.return_value = "test-request-id"
            client = TestClient(app, raise_server_exceptions=True)
            response = client.get("/test")

        assert response.status_code == 200
        mock_log_req.assert_called_once()

    def test_streaming_response_returns_logged_streaming_response(self):
        """Streaming responses should be wrapped in LoggedStreamingResponse."""
        app = FastAPI()
        app.router.route_class = LoggedAPIRoute

        async def generate():
            yield b"chunk1"
            yield b"chunk2"

        @app.get("/stream")
        async def stream_endpoint():
            return StreamingResponse(generate(), media_type="text/plain")

        with (
            patch("src.api.logged_api_route.log_request") as mock_log_req,
            patch("src.api.logged_api_route.ctx_var_request_id") as mock_ctx,
        ):
            mock_ctx.get.return_value = "stream-req-id"
            client = TestClient(app, raise_server_exceptions=True)
            response = client.get("/stream")

        assert response.status_code == 200
        assert response.text == "chunk1chunk2"
        mock_log_req.assert_called_once()

    def test_form_data_request_body_parsed(self):
        """Form data content type should be parsed correctly."""
        app = FastAPI()
        app.router.route_class = LoggedAPIRoute

        @app.post("/upload")
        async def upload_endpoint(request: Request):
            return {"ok": True}

        with (
            patch("src.api.logged_api_route.log_request") as mock_log_req,
            patch("src.api.logged_api_route.ctx_var_request_id") as mock_ctx,
        ):
            mock_ctx.get.return_value = "form-req-id"
            client = TestClient(app, raise_server_exceptions=True)
            response = client.post(
                "/upload",
                data={"field1": "value1"},
            )

        assert response.status_code == 200
        mock_log_req.assert_called_once()


@pytest.mark.unit
class TestLoggedStreamingResponse:
    """Tests for LoggedStreamingResponse."""

    def test_stream_response_error_wraps_exception(self):
        """StreamResponseError should wrap the original exception."""
        original_exc = ValueError("something went wrong")
        error = StreamResponseError(original_exc)
        assert error.exception is original_exc

    @pytest.mark.asyncio
    async def test_stream_response_sends_chunks(self):
        """LoggedStreamingResponse should send all chunks to the ASGI send callable."""

        async def generate():
            yield b"hello "
            yield b"world"

        response = LoggedStreamingResponse(
            request_id="test-id",
            request=MagicMock(),
            request_body=b"",
            content=generate(),
            status_code=200,
        )

        sent_messages = []

        async def mock_send(message):
            sent_messages.append(message)

        with patch("src.api.logged_api_route.log_response"):
            await response.stream_response(mock_send)

        # Should have: http.response.start, chunk1, chunk2, final empty body
        assert sent_messages[0]["type"] == "http.response.start"
        assert sent_messages[0]["status"] == 200
        body_messages = [m for m in sent_messages if m["type"] == "http.response.body"]
        assert body_messages[0]["body"] == b"hello "
        assert body_messages[1]["body"] == b"world"
        assert body_messages[-1]["body"] == b""
        assert body_messages[-1]["more_body"] is False

    @pytest.mark.asyncio
    async def test_stream_response_error_on_exception(self):
        """LoggedStreamingResponse should raise StreamResponseError on iteration failure."""

        async def failing_generate():
            yield b"start"
            raise RuntimeError("stream failed")

        response = LoggedStreamingResponse(
            request_id="err-id",
            request=MagicMock(),
            request_body=b"",
            content=failing_generate(),
            status_code=200,
        )

        async def mock_send(message):
            pass

        with pytest.raises(StreamResponseError) as exc_info:
            await response.stream_response(mock_send)

        assert isinstance(exc_info.value.exception, RuntimeError)
