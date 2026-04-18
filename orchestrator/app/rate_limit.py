"""Rate limiting utilities for the orchestrator.

Storage backend is configured via ``RATE_LIMIT_STORAGE_URI`` in settings:

  memory://        In-process storage — resets on restart, not shared across
                   replicas.  Safe default for development and tests.

  redis://host/db  Redis-backed storage — survives restarts and is shared
                   across all replicas.  Use this in production.

Example Railway production env::

    RATE_LIMIT_STORAGE_URI=redis://redis:6379/0
"""
import re
from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.config import get_settings


def _get_user_id_or_ip(request: Request) -> str:
    """Return a per-user rate-limit key, falling back to IP.

    Precedence:
    1. ``request.state.user_id`` — set by auth middleware for authenticated reqs
    2. First 16 chars of the Bearer token — identifies API-key callers
    3. Client IP address — unauthenticated fallback
    """
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return f"user:{user_id}"

    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        return f"token:{token[:16]}"

    return get_remote_address(request)


def _make_limiter(storage_uri: str) -> Limiter:
    """Create a :class:`~slowapi.Limiter` bound to *storage_uri*.

    Extracted into a factory so tests can instantiate a fresh limiter with
    ``memory://`` without mutating the module-level singleton.
    """
    return Limiter(key_func=get_remote_address, storage_uri=storage_uri)


# Module-level singleton consumed by all ``@limiter.limit(...)`` decorators.
# storage_uri is read once at import time from settings (lru_cache'd).
limiter: Limiter = _make_limiter(get_settings().rate_limit_storage_uri)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Return a 429 JSON response with a ``Retry-After`` header.

    Parses the limit string from *exc* (e.g. ``"60 per 1 minute"``) to derive
    a sensible ``Retry-After`` value.  Defaults to 60 seconds when parsing
    fails.
    """
    retry_after = 60
    if hasattr(exc, "detail") and exc.detail:
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

    response = JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Please try again later."},
    )
    response.headers["Retry-After"] = str(retry_after)
    return response
