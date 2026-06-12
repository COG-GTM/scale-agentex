"""Unit tests for RequestLoggingMiddleware.

Tests that the middleware assigns a unique request ID context var for each request.
Target: 100% coverage of src/api/RequestLoggingMiddleware.py (19 lines).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import FastAPI, Request
from src.api.RequestLoggingMiddleware import RequestLoggingMiddleware
from src.utils.logging import ctx_var_request_id
from starlette.testclient import TestClient


@pytest.mark.unit
class TestRequestLoggingMiddleware:
    """Unit tests for RequestLoggingMiddleware."""

    def test_sets_unique_request_id(self):
        """Each request should get a unique hex request ID set in context var."""
        app = FastAPI()
        app.add_middleware(RequestLoggingMiddleware)

        captured_ids = []

        @app.get("/capture")
        async def capture_endpoint(request: Request):
            captured_ids.append(ctx_var_request_id.get())
            return {"ok": True}

        client = TestClient(app, raise_server_exceptions=True)

        client.get("/capture")
        client.get("/capture")

        assert len(captured_ids) == 2
        # Each request gets a distinct ID
        assert captured_ids[0] != captured_ids[1]
        # IDs are hex strings (uuid4 without hyphens)
        assert all(len(rid) == 32 for rid in captured_ids)
        assert all(all(c in "0123456789abcdef" for c in rid) for rid in captured_ids)

    def test_request_id_is_available_in_downstream(self):
        """The request ID should be accessible to downstream route handlers."""
        app = FastAPI()
        app.add_middleware(RequestLoggingMiddleware)

        @app.get("/id")
        async def id_endpoint(request: Request):
            return {"request_id": ctx_var_request_id.get()}

        client = TestClient(app, raise_server_exceptions=True)
        response = client.get("/id")

        assert response.status_code == 200
        request_id = response.json()["request_id"]
        assert len(request_id) == 32

    def test_middleware_passes_response_through(self):
        """The middleware should not alter the response from downstream."""
        app = FastAPI()
        app.add_middleware(RequestLoggingMiddleware)

        @app.get("/passthrough")
        async def passthrough():
            return {"data": [1, 2, 3]}

        client = TestClient(app, raise_server_exceptions=True)
        response = client.get("/passthrough")

        assert response.status_code == 200
        assert response.json() == {"data": [1, 2, 3]}

    def test_different_methods_get_unique_ids(self):
        """POST, PUT, DELETE should all get unique request IDs."""
        app = FastAPI()
        app.add_middleware(RequestLoggingMiddleware)

        captured_ids = []

        @app.api_route("/multi", methods=["GET", "POST", "PUT", "DELETE"])
        async def multi_endpoint(request: Request):
            captured_ids.append(ctx_var_request_id.get())
            return {"ok": True}

        client = TestClient(app, raise_server_exceptions=True)
        client.get("/multi")
        client.post("/multi")
        client.put("/multi")
        client.delete("/multi")

        assert len(captured_ids) == 4
        assert len(set(captured_ids)) == 4  # All unique

    def test_uuid4_hex_called(self):
        """Verify uuid4 is called to generate the request ID."""
        app = FastAPI()
        app.add_middleware(RequestLoggingMiddleware)

        @app.get("/uuid-check")
        async def uuid_check():
            return {"id": ctx_var_request_id.get()}

        with patch("src.api.RequestLoggingMiddleware.uuid4") as mock_uuid:
            mock_uuid.return_value = type("MockUUID", (), {"hex": "a" * 32})()
            client = TestClient(app, raise_server_exceptions=True)
            response = client.get("/uuid-check")

        assert response.status_code == 200
        assert response.json()["id"] == "a" * 32
        mock_uuid.assert_called_once()
