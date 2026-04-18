"""Tests for CORS configuration and rate limiting."""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

# Import rate limit utilities directly -- no dependency on main.py
from app.rate_limit import limiter, _get_user_id_or_ip, rate_limit_exceeded_handler, _make_limiter


# --- CORS Tests ---

class TestCORSConfiguration:
    """Tests for CORS environment-based configuration."""

    def test_cors_default_origins_include_localhost(self):
        """Test that default CORS origins include localhost."""
        from app.config import get_settings
        settings = get_settings()
        # The default should include localhost:3000
        assert "http://localhost:3000" in settings.cors_allowed_origins

    def test_cors_config_is_string(self):
        """Test that CORS config is a comma-separated string."""
        from app.config import get_settings
        settings = get_settings()
        # Should be a string
        assert isinstance(settings.cors_allowed_origins, str)
        # Should contain localhost:3000
        assert "localhost:3000" in settings.cors_allowed_origins


# --- Rate Limiting Key Function Tests ---

class TestRateLimitKeyFunctions:
    """Tests for rate limiting key functions."""

    def test_get_user_id_or_ip_uses_user_id_from_state(self):
        """Test that _get_user_id_or_ip uses user ID from request state."""
        from starlette.requests import Request

        # Create a mock request with user_id in state
        mock_request = MagicMock()
        mock_request.state.user_id = "user-123"
        mock_request.headers = {}

        result = _get_user_id_or_ip(mock_request)
        assert result == "user:user-123"

    def test_get_user_id_or_ip_uses_token_from_auth_header(self):
        """Test that _get_user_id_or_ip uses token from Authorization header."""
        from starlette.requests import Request

        # Create a mock request with Authorization header but no user_id in state
        mock_request = MagicMock()
        mock_request.state = MagicMock()
        del mock_request.state.user_id
        mock_request.headers = {"Authorization": "Bearer sk-test-api-key-12345"}

        result = _get_user_id_or_ip(mock_request)
        assert result.startswith("token:")
        assert "sk-test-api-key" in result

    def test_get_user_id_or_ip_falls_back_to_ip(self):
        """Test that _get_user_id_or_ip falls back to IP address."""
        from starlette.requests import Request

        # Create a mock request with no user_id or auth header
        mock_request = MagicMock()
        mock_request.state = MagicMock()
        mock_request.headers = {}
        mock_request.client = MagicMock()
        mock_request.client.host = "192.168.1.1"

        result = _get_user_id_or_ip(mock_request)
        assert result == "192.168.1.1"


# --- Rate Limit Exceeded Handler Tests ---

class TestRateLimitExceededHandler:
    """Tests for the rate limit exceeded handler."""

    def test_handler_returns_429_status(self):
        """Test that handler returns 429 status code."""
        from fastapi import Request

        mock_request = MagicMock(spec=Request)
        mock_exc = RateLimitExceeded("60 per 1 minute")

        response = rate_limit_exceeded_handler(mock_request, mock_exc)

        assert response.status_code == 429

    def test_handler_includes_retry_after_header(self):
        """Test that handler includes Retry-After header."""
        from fastapi import Request

        mock_request = MagicMock(spec=Request)
        mock_exc = RateLimitExceeded("60 per 1 minute")

        response = rate_limit_exceeded_handler(mock_request, mock_exc)

        assert "retry-after" in response.headers
        # Should be a valid integer string
        retry_after = int(response.headers["retry-after"])
        assert retry_after > 0

    def test_handler_parses_minute_limit(self):
        """Test that handler correctly parses minute-based limits."""
        from fastapi import Request

        mock_request = MagicMock(spec=Request)
        mock_exc = RateLimitExceeded("30 per 1 minute")

        response = rate_limit_exceeded_handler(mock_request, mock_exc)

        retry_after = int(response.headers["retry-after"])
        # 1 minute = 60 seconds
        assert retry_after == 60

    def test_handler_parses_second_limit(self):
        """Test that handler correctly parses second-based limits."""
        from fastapi import Request

        mock_request = MagicMock(spec=Request)
        mock_exc = RateLimitExceeded("10 per 30 second")

        response = rate_limit_exceeded_handler(mock_request, mock_exc)

        retry_after = int(response.headers["retry-after"])
        # 30 seconds
        assert retry_after == 30

    def test_handler_default_retry_after_on_parse_error(self):
        """Test that handler defaults to 60 seconds when parsing fails."""
        from fastapi import Request

        mock_request = MagicMock(spec=Request)
        # Unusual format that won't match the regex
        mock_exc = RateLimitExceeded("some weird format")

        response = rate_limit_exceeded_handler(mock_request, mock_exc)

        retry_after = int(response.headers["retry-after"])
        assert retry_after == 60  # Default


# --- Integration Tests for Rate Limiting ---

class TestRateLimitingIntegration:
    """Integration tests for rate limiting on endpoints."""

    def test_rate_limit_429_response_format(self):
        """Test that 429 response includes proper format."""
        from fastapi import Request

        mock_request = MagicMock(spec=Request)
        mock_exc = RateLimitExceeded("60 per 1 minute")

        response = rate_limit_exceeded_handler(mock_request, mock_exc)

        assert response.status_code == 429
        assert "retry-after" in response.headers

        # Check the response body
        import json
        body = json.loads(response.body)
        assert "detail" in body
        assert "rate limit" in body["detail"].lower()


# --- Rate Limit Storage Configuration Tests ---

class TestRateLimitStorageConfig:
    """Tests for rate limit storage backend configuration.

    Verifies that ``_make_limiter`` correctly wires the ``limits``-library
    storage backend based on ``rate_limit_storage_uri`` in settings, and that
    the module-level singleton uses the configured URI.
    """

    def test_default_storage_uri_is_memory(self):
        """Default ``rate_limit_storage_uri`` must be ``memory://`` for test safety."""
        from app.config import get_settings
        settings = get_settings()
        assert settings.rate_limit_storage_uri == "memory://"

    def test_make_limiter_returns_limiter_instance(self):
        """_make_limiter must return a slowapi Limiter regardless of storage URI."""
        result = _make_limiter("memory://")
        assert isinstance(result, Limiter)

    def test_make_limiter_each_call_returns_fresh_instance(self):
        """Each _make_limiter call must produce an independent object."""
        lim1 = _make_limiter("memory://")
        lim2 = _make_limiter("memory://")
        assert lim1 is not lim2

    def test_module_limiter_is_limiter_instance(self):
        """Module-level ``limiter`` singleton must be a slowapi Limiter."""
        assert isinstance(limiter, Limiter)

    def test_memory_storage_class_name(self):
        """Storage class for ``memory://`` must be MemoryStorage."""
        lim = _make_limiter("memory://")
        # Access via slowapi internals: Limiter wraps a limits.strategies.* object
        # which exposes .storage
        storage = lim._limiter.storage
        assert "Memory" in type(storage).__name__

    def test_make_limiter_redis_uri_returns_limiter(self):
        """_make_limiter must accept a redis:// URI without raising at creation time.

        The ``limits`` library creates the Redis client lazily (on first counter
        increment), so Limiter construction succeeds even without a live Redis.
        """
        # No connection is made during construction -- this must not raise
        lim = _make_limiter("redis://localhost:6379/0")
        assert isinstance(lim, Limiter)

    def test_redis_and_memory_limiters_have_different_storage_types(self):
        """Redis-backed and memory-backed limiters must use different storage classes."""
        mem_lim = _make_limiter("memory://")
        redis_lim = _make_limiter("redis://localhost:6379/0")

        mem_storage_name = type(mem_lim._limiter.storage).__name__
        redis_storage_name = type(redis_lim._limiter.storage).__name__

        assert mem_storage_name != redis_storage_name
        assert "Memory" in mem_storage_name
        assert "Redis" in redis_storage_name

    def test_storage_uri_override_via_settings(self):
        """Overriding RATE_LIMIT_STORAGE_URI must be picked up by a new settings instance."""
        import os
        from app.config import Settings

        # Bypass the lru_cache by instantiating Settings directly
        overridden = Settings(rate_limit_storage_uri="redis://redis:6379/1")
        assert overridden.rate_limit_storage_uri == "redis://redis:6379/1"
        new_lim = _make_limiter(overridden.rate_limit_storage_uri)
        assert isinstance(new_lim, Limiter)
        assert "Redis" in type(new_lim._limiter.storage).__name__
