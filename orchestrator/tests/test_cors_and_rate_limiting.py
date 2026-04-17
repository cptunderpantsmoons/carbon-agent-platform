"""Tests for CORS configuration and rate limiting."""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

# Import rate limit utilities directly - no dependency on main.py
from app.rate_limit import limiter, _get_user_id_or_ip, rate_limit_exceeded_handler


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
        
        # Create a mock request with Authorization header
        mock_request = MagicMock()
        mock_request.state = MagicMock()
        del mock_request.state.user_id  # No user_id in state
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
        # This test verifies the handler works by testing it directly
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
