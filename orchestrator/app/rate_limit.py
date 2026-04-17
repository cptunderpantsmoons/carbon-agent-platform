"""Rate limiting utilities for the orchestrator."""
import re
from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded


def _get_user_id_or_ip(request: Request) -> str:
    """Get user ID for rate limiting, fall back to IP address.

    Used for authenticated routes where we want per-user rate limiting.
    """
    # Try to get user ID from request state (set by auth middleware)
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return f"user:{user_id}"

    # Fall back to Authorization header API key for identification
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        # Use a hash of the token to avoid logging raw tokens
        token = auth_header[7:]
        return f"token:{token[:16]}"  # Use first 16 chars as identifier

    # Final fallback to IP address
    return get_remote_address(request)


# Rate limiter instance - uses remote IP as default key
limiter = Limiter(key_func=get_remote_address)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Custom rate limit exceeded handler that includes Retry-After header."""
    response = JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Please try again later."},
    )
    # Default to 60 seconds for safety
    retry_after = 60
    if hasattr(exc, "detail") and exc.detail:
        # Try to extract the retry time from the limit string
        # Format is like "60 per 1 minute" or "30 per 1 minute"
        match = re.search(r"per\s+(\d+)\s+(minute|second|hour)", str(exc.detail))
        if match:
            amount = int(match.group(1))
            unit = match.group(2)
            if unit == "second":
                retry_after = amount
            elif unit == "minute":
                retry_after = amount * 60
            elif unit == "hour":
                retry_after = amount * 3600
    response.headers["Retry-After"] = str(retry_after)
    return response
