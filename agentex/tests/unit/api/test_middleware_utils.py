"""Unit tests for middleware_utils.py.

Tests the shared middleware utility functions:
- is_whitelisted_route (prefix/boundary matching)
- verify_agent_identity (DB lookup success, not found, exception)
- verify_agent_api_key (DB lookup success, not found, exception)
- verify_auth_gateway (success, exception)
- get_request_headers_to_forward (header filtering)
- resolve_authorization_enabled (truthy/falsy env values)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request
from fastapi.responses import JSONResponse
from src.api.middleware_utils import (
    DROP_HEADERS,
    WHITELISTED_ROUTES,
    get_request_headers_to_forward,
    is_whitelisted_route,
    resolve_authorization_enabled,
    verify_agent_api_key,
    verify_agent_identity,
    verify_auth_gateway,
)


@pytest.mark.unit
class TestIsWhitelistedRoute:
    """Tests for is_whitelisted_route function."""

    def test_exact_match(self):
        """Exact path matches should be whitelisted."""
        for route in WHITELISTED_ROUTES:
            assert is_whitelisted_route(route) is True

    def test_sub_path_match(self):
        """Sub-paths under whitelisted routes should be whitelisted."""
        assert is_whitelisted_route("/health/live") is True
        assert is_whitelisted_route("/docs/openapi") is True
        assert is_whitelisted_route("/agents/register/callback") is True

    def test_non_whitelisted_route(self):
        """Routes not matching any whitelist entry should not be whitelisted."""
        assert is_whitelisted_route("/tasks") is False
        assert is_whitelisted_route("/agents/list") is False
        assert is_whitelisted_route("/protected") is False

    def test_prefix_boundary_no_false_match(self):
        """Routes that only share a prefix (no boundary '/') should NOT match."""
        # /agents/register should NOT whitelist /agents/register-build
        assert is_whitelisted_route("/agents/register-build") is False
        assert is_whitelisted_route("/healthcheck-extended") is False

    def test_custom_whitelist(self):
        """Custom whitelist set should be respected."""
        custom = {"/custom", "/api/v2"}
        assert is_whitelisted_route("/custom", custom) is True
        assert is_whitelisted_route("/custom/sub", custom) is True
        assert is_whitelisted_route("/api/v2", custom) is True
        assert is_whitelisted_route("/api/v2/users", custom) is True
        assert is_whitelisted_route("/api/v3", custom) is False

    def test_empty_path(self):
        """Empty path should not be whitelisted."""
        assert is_whitelisted_route("") is False

    def test_root_path(self):
        """Root path should not be whitelisted unless explicitly listed."""
        assert is_whitelisted_route("/") is False


@pytest.mark.unit
@pytest.mark.asyncio
class TestVerifyAgentIdentity:
    """Tests for verify_agent_identity function."""

    async def test_valid_agent_identity(self):
        """Valid agent identity found in DB should return None (success)."""
        mock_agent = MagicMock()
        mock_agent.id = "agent-123"

        mock_session = AsyncMock()
        mock_session.scalar = AsyncMock(return_value=mock_agent)

        mock_session_maker = MagicMock()
        mock_session_maker.return_value.__aenter__ = AsyncMock(
            return_value=mock_session
        )
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)

        request = MagicMock(spec=Request)
        request.state = MagicMock()

        with patch(
            "src.api.middleware_utils.middleware_async_read_only_session_maker",
            return_value=mock_session_maker,
        ):
            result = await verify_agent_identity(request, "agent-123")

        assert result is None
        assert request.state.agent_identity == "agent-123"

    async def test_invalid_agent_identity(self):
        """Invalid agent identity not found in DB should return 401."""
        mock_session = AsyncMock()
        mock_session.scalar = AsyncMock(return_value=None)

        mock_session_maker = MagicMock()
        mock_session_maker.return_value.__aenter__ = AsyncMock(
            return_value=mock_session
        )
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)

        request = MagicMock(spec=Request)
        request.state = MagicMock()

        with patch(
            "src.api.middleware_utils.middleware_async_read_only_session_maker",
            return_value=mock_session_maker,
        ):
            result = await verify_agent_identity(request, "nonexistent")

        assert isinstance(result, JSONResponse)
        assert result.status_code == 401

    async def test_agent_identity_db_exception(self):
        """DB exception during agent identity verification should return 500."""
        mock_session_maker = MagicMock()
        mock_session_maker.return_value.__aenter__ = AsyncMock(
            side_effect=Exception("DB connection failed")
        )
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)

        request = MagicMock(spec=Request)
        request.state = MagicMock()

        with patch(
            "src.api.middleware_utils.middleware_async_read_only_session_maker",
            return_value=mock_session_maker,
        ):
            result = await verify_agent_identity(request, "agent-123")

        assert isinstance(result, JSONResponse)
        assert result.status_code == 500


@pytest.mark.unit
@pytest.mark.asyncio
class TestVerifyAgentApiKey:
    """Tests for verify_agent_api_key function."""

    async def test_valid_api_key(self):
        """Valid API key found in DB should return None (success)."""
        mock_api_key_orm = MagicMock()
        mock_api_key_orm.agent_id = "agent-456"

        mock_session = AsyncMock()
        mock_session.scalar = AsyncMock(return_value=mock_api_key_orm)

        mock_session_maker = MagicMock()
        mock_session_maker.return_value.__aenter__ = AsyncMock(
            return_value=mock_session
        )
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)

        request = MagicMock(spec=Request)
        request.state = MagicMock()

        with patch(
            "src.api.middleware_utils.middleware_async_read_only_session_maker",
            return_value=mock_session_maker,
        ):
            result = await verify_agent_api_key(request, "valid-key-123")

        assert result is None
        assert request.state.agent_identity == "agent-456"

    async def test_invalid_api_key(self):
        """Invalid API key not found in DB should return 401."""
        mock_session = AsyncMock()
        mock_session.scalar = AsyncMock(return_value=None)

        mock_session_maker = MagicMock()
        mock_session_maker.return_value.__aenter__ = AsyncMock(
            return_value=mock_session
        )
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)

        request = MagicMock(spec=Request)
        request.state = MagicMock()

        with patch(
            "src.api.middleware_utils.middleware_async_read_only_session_maker",
            return_value=mock_session_maker,
        ):
            result = await verify_agent_api_key(request, "bad-key")

        assert isinstance(result, JSONResponse)
        assert result.status_code == 401

    async def test_api_key_db_exception(self):
        """DB exception during API key verification should return 500."""
        mock_session_maker = MagicMock()
        mock_session_maker.return_value.__aenter__ = AsyncMock(
            side_effect=Exception("DB connection failed")
        )
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)

        request = MagicMock(spec=Request)
        request.state = MagicMock()

        with patch(
            "src.api.middleware_utils.middleware_async_read_only_session_maker",
            return_value=mock_session_maker,
        ):
            result = await verify_agent_api_key(request, "some-key")

        assert isinstance(result, JSONResponse)
        assert result.status_code == 500


@pytest.mark.unit
@pytest.mark.asyncio
class TestVerifyAuthGateway:
    """Tests for verify_auth_gateway function."""

    async def test_successful_verification(self):
        """Successful auth gateway verification should set principal_context."""
        mock_principal = {"user_id": "user-1", "account_id": "acct-1"}
        mock_auth_gateway = AsyncMock()
        mock_auth_gateway.verify_headers = AsyncMock(return_value=mock_principal)

        request = MagicMock(spec=Request)
        request.state = MagicMock()
        request.url = MagicMock()
        request.url.path = "/tasks"
        request.method = "GET"
        request.headers = {
            "authorization": "Bearer token",
            "accept": "application/json",
        }

        result = await verify_auth_gateway(request, mock_auth_gateway)

        assert result is None
        assert request.state.principal_context == mock_principal

    async def test_failed_verification(self):
        """Failed auth gateway verification should return 401."""
        mock_auth_gateway = AsyncMock()
        mock_auth_gateway.verify_headers = AsyncMock(
            side_effect=Exception("Auth service unavailable")
        )

        request = MagicMock(spec=Request)
        request.state = MagicMock()
        request.url = MagicMock()
        request.url.path = "/tasks"
        request.method = "GET"
        request.headers = {"authorization": "Bearer bad-token"}

        result = await verify_auth_gateway(request, mock_auth_gateway)

        assert isinstance(result, JSONResponse)
        assert result.status_code == 401


@pytest.mark.unit
class TestGetRequestHeadersToForward:
    """Tests for get_request_headers_to_forward function."""

    def test_excludes_drop_headers(self):
        """Headers in DROP_HEADERS should be excluded."""
        request = MagicMock(spec=Request)
        request.headers = {
            "authorization": "Bearer token",
            "content-length": "100",
            "host": "example.com",
            "connection": "keep-alive",
            "x-custom": "value",
        }

        result = get_request_headers_to_forward(request)

        assert "content-length" not in result
        assert "host" not in result
        assert "connection" not in result
        assert result["authorization"] == "Bearer token"
        assert result["x-custom"] == "value"

    def test_lowercases_header_names(self):
        """Header names should be lowercased in output."""
        request = MagicMock(spec=Request)
        request.headers = {
            "X-Custom-Header": "value",
            "Authorization": "Bearer token",
        }

        result = get_request_headers_to_forward(request)

        assert "x-custom-header" in result
        assert "authorization" in result

    def test_empty_headers(self):
        """Empty headers should return empty dict."""
        request = MagicMock(spec=Request)
        request.headers = {}

        result = get_request_headers_to_forward(request)

        assert result == {}

    def test_custom_exclude_set(self):
        """Custom exclude set should override defaults."""
        request = MagicMock(spec=Request)
        request.headers = {
            "authorization": "Bearer token",
            "x-custom": "value",
        }

        result = get_request_headers_to_forward(
            request, exclude_headers={"authorization"}
        )

        assert "authorization" not in result
        assert result["x-custom"] == "value"

    def test_all_default_drop_headers_present(self):
        """Verify all DROP_HEADERS are properly excluded."""
        request = MagicMock(spec=Request)
        headers = dict.fromkeys(DROP_HEADERS, "test-value")
        headers["x-keep"] = "keep-me"
        request.headers = headers

        result = get_request_headers_to_forward(request)

        for h in DROP_HEADERS:
            assert h not in result
        assert result["x-keep"] == "keep-me"


@pytest.mark.unit
class TestResolveAuthorizationEnabled:
    """Tests for resolve_authorization_enabled function."""

    def test_truthy_value(self):
        """Non-empty string should resolve to True."""
        assert resolve_authorization_enabled("http://auth-url") is True

    def test_falsy_empty_string(self):
        """Empty string should resolve to False."""
        assert resolve_authorization_enabled("") is False

    def test_falsy_none(self):
        """None should resolve to False."""
        assert resolve_authorization_enabled(None) is False
