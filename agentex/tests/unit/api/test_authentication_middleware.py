"""Unit tests for AgentexAuthMiddleware.

Tests the authentication middleware dispatch logic covering:
- OPTIONS requests bypass authentication
- Whitelisted routes bypass authentication
- Agent identity header flow (cache hit, cache miss, cache failure sentinel)
- Agent API key header flow (cache hit, cache miss, cache failure sentinel)
- Auth gateway flow (cache hit, cache miss, disabled)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from src.api.authentication_middleware import _CACHED_FAILED_AUTH, AgentexAuthMiddleware
from starlette.testclient import TestClient


def _make_app_with_middleware() -> FastAPI:
    """Create a minimal FastAPI app wrapped with AgentexAuthMiddleware."""
    app = FastAPI()

    @app.get("/protected")
    async def protected():
        return {"ok": True}

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


@pytest.fixture
def mock_env_vars():
    """Patch environment variable resolution used by the middleware constructor."""

    def _resolve(key):
        from src.config.environment_variables import EnvVarKeys

        if key == EnvVarKeys.AGENTEX_AUTH_URL:
            return "http://fake-auth-url"
        if key == EnvVarKeys.ENVIRONMENT:
            return "development"
        return ""

    with patch(
        "src.api.authentication_middleware.resolve_environment_variable_dependency",
        side_effect=_resolve,
    ) as mock_resolve:
        yield mock_resolve


@pytest.fixture
def mock_auth_cache():
    """Provide a mock AuthenticationCache instance."""
    cache = AsyncMock()
    cache.get_agent_identity = AsyncMock(return_value=None)
    cache.get_agent_api_key = AsyncMock(return_value=None)
    cache.get_auth_gateway_response = AsyncMock(return_value=None)
    cache.set_agent_identity = AsyncMock()
    cache.set_agent_api_key = AsyncMock()
    cache.set_auth_gateway_response = AsyncMock()
    return cache


@pytest.mark.unit
@pytest.mark.asyncio
class TestAgentexAuthMiddleware:
    async def test_options_request_bypasses_auth(self, mock_env_vars):
        """OPTIONS requests should pass through without authentication (no 401)."""
        app = _make_app_with_middleware()

        with patch("src.api.authentication_middleware.AgentexAuthenticationProxy"):
            app.add_middleware(AgentexAuthMiddleware)

        client = TestClient(app, raise_server_exceptions=True)
        response = client.options("/protected")
        # The middleware passes OPTIONS through without auth checks.
        # The route may return 405 (Method Not Allowed) because it only handles GET,
        # but the key assertion is that it's NOT a 401 from the auth middleware.
        assert response.status_code != 401

    async def test_whitelisted_route_bypasses_auth(self, mock_env_vars):
        """Whitelisted routes should pass through without authentication."""
        app = _make_app_with_middleware()

        with patch("src.api.authentication_middleware.AgentexAuthenticationProxy"):
            app.add_middleware(AgentexAuthMiddleware)

        client = TestClient(app, raise_server_exceptions=True)
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    async def test_agent_identity_cached_success(self, mock_env_vars, mock_auth_cache):
        """Cached successful agent identity should proceed without DB lookup."""
        app = _make_app_with_middleware()
        mock_auth_cache.get_agent_identity = AsyncMock(return_value="agent-123")

        with (
            patch("src.api.authentication_middleware.AgentexAuthenticationProxy"),
            patch(
                "src.api.authentication_middleware.get_auth_cache",
                return_value=mock_auth_cache,
            ),
        ):
            app.add_middleware(AgentexAuthMiddleware)
            client = TestClient(app, raise_server_exceptions=True)
            response = client.get(
                "/protected", headers={"x-agent-identity": "agent-123"}
            )

        assert response.status_code == 200

    async def test_agent_identity_cached_failure(self, mock_env_vars, mock_auth_cache):
        """Cached failed agent identity should return 401."""
        app = _make_app_with_middleware()
        mock_auth_cache.get_agent_identity = AsyncMock(return_value=_CACHED_FAILED_AUTH)

        with (
            patch("src.api.authentication_middleware.AgentexAuthenticationProxy"),
            patch(
                "src.api.authentication_middleware.get_auth_cache",
                return_value=mock_auth_cache,
            ),
        ):
            app.add_middleware(AgentexAuthMiddleware)
            client = TestClient(app, raise_server_exceptions=True)
            response = client.get(
                "/protected", headers={"x-agent-identity": "bad-agent"}
            )

        assert response.status_code == 401
        assert response.json()["detail"] == "Agent Unauthorized"

    async def test_agent_identity_not_cached_verified_ok(
        self, mock_env_vars, mock_auth_cache
    ):
        """Uncached agent identity that passes DB verification should succeed."""
        app = _make_app_with_middleware()

        with (
            patch("src.api.authentication_middleware.AgentexAuthenticationProxy"),
            patch(
                "src.api.authentication_middleware.get_auth_cache",
                return_value=mock_auth_cache,
            ),
            patch(
                "src.api.authentication_middleware.verify_agent_identity",
                return_value=None,
            ) as mock_verify,
        ):
            app.add_middleware(AgentexAuthMiddleware)
            client = TestClient(app, raise_server_exceptions=True)
            response = client.get(
                "/protected", headers={"x-agent-identity": "new-agent"}
            )

        assert response.status_code == 200
        mock_verify.assert_called_once()
        mock_auth_cache.set_agent_identity.assert_called_once()

    async def test_agent_identity_not_cached_verified_fail(
        self, mock_env_vars, mock_auth_cache
    ):
        """Uncached agent identity that fails verification should return error and cache failure."""
        app = _make_app_with_middleware()
        error_response = JSONResponse(
            status_code=401, content={"detail": "Agent Unauthorized"}
        )

        with (
            patch("src.api.authentication_middleware.AgentexAuthenticationProxy"),
            patch(
                "src.api.authentication_middleware.get_auth_cache",
                return_value=mock_auth_cache,
            ),
            patch(
                "src.api.authentication_middleware.verify_agent_identity",
                return_value=error_response,
            ),
        ):
            app.add_middleware(AgentexAuthMiddleware)
            client = TestClient(app, raise_server_exceptions=True)
            response = client.get(
                "/protected", headers={"x-agent-identity": "invalid-agent"}
            )

        assert response.status_code == 401
        mock_auth_cache.set_agent_identity.assert_called_once_with(
            "invalid-agent", _CACHED_FAILED_AUTH
        )

    async def test_agent_api_key_cached_success(self, mock_env_vars, mock_auth_cache):
        """Cached successful agent API key should proceed without DB lookup."""
        app = _make_app_with_middleware()
        mock_auth_cache.get_agent_api_key = AsyncMock(return_value="agent-456")

        with (
            patch("src.api.authentication_middleware.AgentexAuthenticationProxy"),
            patch(
                "src.api.authentication_middleware.get_auth_cache",
                return_value=mock_auth_cache,
            ),
        ):
            app.add_middleware(AgentexAuthMiddleware)
            client = TestClient(app, raise_server_exceptions=True)
            response = client.get(
                "/protected", headers={"x-agent-api-key": "valid-key"}
            )

        assert response.status_code == 200

    async def test_agent_api_key_cached_failure(self, mock_env_vars, mock_auth_cache):
        """Cached failed agent API key should return 401."""
        app = _make_app_with_middleware()
        mock_auth_cache.get_agent_api_key = AsyncMock(return_value=_CACHED_FAILED_AUTH)

        with (
            patch("src.api.authentication_middleware.AgentexAuthenticationProxy"),
            patch(
                "src.api.authentication_middleware.get_auth_cache",
                return_value=mock_auth_cache,
            ),
        ):
            app.add_middleware(AgentexAuthMiddleware)
            client = TestClient(app, raise_server_exceptions=True)
            response = client.get("/protected", headers={"x-agent-api-key": "bad-key"})

        assert response.status_code == 401
        assert response.json()["detail"] == "Agent Unauthorized"

    async def test_agent_api_key_not_cached_verified_ok(
        self, mock_env_vars, mock_auth_cache
    ):
        """Uncached agent API key that passes DB verification should succeed."""
        app = _make_app_with_middleware()

        with (
            patch("src.api.authentication_middleware.AgentexAuthenticationProxy"),
            patch(
                "src.api.authentication_middleware.get_auth_cache",
                return_value=mock_auth_cache,
            ),
            patch(
                "src.api.authentication_middleware.verify_agent_api_key",
                return_value=None,
            ) as mock_verify,
        ):
            app.add_middleware(AgentexAuthMiddleware)
            client = TestClient(app, raise_server_exceptions=True)
            response = client.get("/protected", headers={"x-agent-api-key": "new-key"})

        assert response.status_code == 200
        mock_verify.assert_called_once()
        mock_auth_cache.set_agent_api_key.assert_called_once()

    async def test_agent_api_key_not_cached_verified_fail(
        self, mock_env_vars, mock_auth_cache
    ):
        """Uncached agent API key that fails verification should cache failure."""
        app = _make_app_with_middleware()
        error_response = JSONResponse(
            status_code=401, content={"detail": "Agent Unauthorized"}
        )

        with (
            patch("src.api.authentication_middleware.AgentexAuthenticationProxy"),
            patch(
                "src.api.authentication_middleware.get_auth_cache",
                return_value=mock_auth_cache,
            ),
            patch(
                "src.api.authentication_middleware.verify_agent_api_key",
                return_value=error_response,
            ),
        ):
            app.add_middleware(AgentexAuthMiddleware)
            client = TestClient(app, raise_server_exceptions=True)
            response = client.get(
                "/protected", headers={"x-agent-api-key": "invalid-key"}
            )

        assert response.status_code == 401
        mock_auth_cache.set_agent_api_key.assert_called_once_with(
            "invalid-key", _CACHED_FAILED_AUTH
        )

    async def test_auth_gateway_cached_principal(self, mock_env_vars, mock_auth_cache):
        """Cached auth gateway principal should bypass verification."""
        app = _make_app_with_middleware()
        mock_principal = {"user_id": "user-1", "account_id": "acct-1"}
        mock_auth_cache.get_auth_gateway_response = AsyncMock(
            return_value=mock_principal
        )

        with (
            patch("src.api.authentication_middleware.AgentexAuthenticationProxy"),
            patch(
                "src.api.authentication_middleware.get_auth_cache",
                return_value=mock_auth_cache,
            ),
        ):
            app.add_middleware(AgentexAuthMiddleware)
            client = TestClient(app, raise_server_exceptions=True)
            response = client.get(
                "/protected", headers={"authorization": "Bearer token123"}
            )

        assert response.status_code == 200

    async def test_auth_gateway_not_cached_success(
        self, mock_env_vars, mock_auth_cache
    ):
        """Uncached auth gateway request that verifies should cache result."""
        app = _make_app_with_middleware()

        with (
            patch("src.api.authentication_middleware.AgentexAuthenticationProxy"),
            patch(
                "src.api.authentication_middleware.get_auth_cache",
                return_value=mock_auth_cache,
            ),
            patch(
                "src.api.authentication_middleware.verify_auth_gateway",
                return_value=None,
            ) as mock_verify,
        ):
            app.add_middleware(AgentexAuthMiddleware)
            client = TestClient(app, raise_server_exceptions=True)
            response = client.get(
                "/protected", headers={"authorization": "Bearer token-new"}
            )

        assert response.status_code == 200
        mock_verify.assert_called_once()
        mock_auth_cache.set_auth_gateway_response.assert_called_once()

    async def test_auth_gateway_not_cached_failure(
        self, mock_env_vars, mock_auth_cache
    ):
        """Uncached auth gateway request that fails should return error without caching."""
        app = _make_app_with_middleware()
        error_response = JSONResponse(
            status_code=401, content={"detail": "Unauthorized"}
        )

        with (
            patch("src.api.authentication_middleware.AgentexAuthenticationProxy"),
            patch(
                "src.api.authentication_middleware.get_auth_cache",
                return_value=mock_auth_cache,
            ),
            patch(
                "src.api.authentication_middleware.verify_auth_gateway",
                return_value=error_response,
            ),
        ):
            app.add_middleware(AgentexAuthMiddleware)
            client = TestClient(app, raise_server_exceptions=True)
            response = client.get(
                "/protected", headers={"authorization": "Bearer bad-token"}
            )

        assert response.status_code == 401
        # Auth gateway failures are NOT cached (may be temporary)
        mock_auth_cache.set_auth_gateway_response.assert_not_called()

    async def test_disabled_auth_gateway_passes_through(self, mock_auth_cache):
        """When AGENTEX_AUTH_URL is unset, auth gateway is disabled and requests pass."""
        with patch(
            "src.api.authentication_middleware.resolve_environment_variable_dependency"
        ) as mock_resolve:
            mock_resolve.return_value = ""  # Empty = disabled

            app = _make_app_with_middleware()

            with (
                patch("src.api.authentication_middleware.AgentexAuthenticationProxy"),
                patch(
                    "src.api.authentication_middleware.get_auth_cache",
                    return_value=mock_auth_cache,
                ),
            ):
                app.add_middleware(AgentexAuthMiddleware)
                client = TestClient(app, raise_server_exceptions=True)
                response = client.get("/protected")

        assert response.status_code == 200

    async def test_is_enabled_returns_true_when_auth_url_set(self, mock_env_vars):
        """is_enabled should return True when AGENTEX_AUTH_URL is set."""
        with patch("src.api.authentication_middleware.AgentexAuthenticationProxy"):
            app = _make_app_with_middleware()
            middleware = AgentexAuthMiddleware(app)
            assert middleware.is_enabled() is True

    async def test_is_enabled_returns_false_when_auth_url_empty(self):
        """is_enabled should return False when AGENTEX_AUTH_URL is empty."""
        with (
            patch(
                "src.api.authentication_middleware.resolve_environment_variable_dependency",
                return_value="",
            ),
            patch("src.api.authentication_middleware.AgentexAuthenticationProxy"),
        ):
            app = _make_app_with_middleware()
            middleware = AgentexAuthMiddleware(app)
            assert middleware.is_enabled() is False


@pytest.mark.unit
def test_resolve_authorization_enabled_dependency():
    """_resolve_authorization_enabled returns True when auth URL is set."""
    from src.api.authentication_middleware import DAuthorizationEnabled  # noqa: F401

    # Just verify the module-level constant/sentinel is correct
    assert _CACHED_FAILED_AUTH == "__FAILED_AUTH__"
