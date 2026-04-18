"""API key injection middleware for Open WebUI frontend requests.

Intercepts requests from the Open WebUI frontend, extracts the Clerk user ID
from the session token, looks up the user's API key from the database, and
rewrites the Authorization header before forwarding to the adapter.
"""
import time

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import MutableHeaders
from starlette.middleware.base import BaseHTTPMiddleware

from app.clerk_auth import get_clerk_jwks_for_verification, verify_clerk_token
from app.models import User, UserStatus

import structlog

logger = structlog.get_logger(__name__)

# In-memory cache for API keys with TTL
_api_key_cache: dict[str, tuple[str, float]] = {}
_API_KEY_CACHE_TTL = 300  # 5 minutes


async def _get_api_key_for_clerk_user(
    db: AsyncSession, clerk_user_id: str
) -> str | None:
    """Look up a user's API key by their Clerk user ID.

    Uses in-memory cache for performance with 5-minute TTL.

    Args:
        db: Database session.
        clerk_user_id: The Clerk user ID.

    Returns:
        The user's API key or None if not found.
    """
    # Check cache first
    if clerk_user_id in _api_key_cache:
        api_key, cached_at = _api_key_cache[clerk_user_id]
        if time.time() - cached_at < _API_KEY_CACHE_TTL:
            return api_key
        else:
            # Cache expired
            del _api_key_cache[clerk_user_id]

    # Look up in database
    result = await db.execute(
        select(User).where(User.clerk_user_id == clerk_user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        return None
    if user.status != UserStatus.ACTIVE:
        return None

    # Cache the API key
    _api_key_cache[clerk_user_id] = (user.api_key, time.time())

    return user.api_key


async def _extract_clerk_user_id_from_request(request: Request) -> str | None:
    """Extract Clerk user ID from request headers or session.

    Tries multiple strategies:
    1. X-Clerk-User-ID header (if set by frontend middleware) — cheapest
    2. Authorization header (Bearer token) — full JWT verification

    Args:
        request: The incoming request.

    Returns:
        Clerk user ID or None.
    """
    # Check for explicit header first (fastest)
    clerk_user_id = request.headers.get("X-Clerk-User-ID")
    if clerk_user_id:
        return clerk_user_id

    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        jwks_provider = request.app.dependency_overrides.get(
            get_clerk_jwks_for_verification,
            get_clerk_jwks_for_verification,
        )
        jwks_override = jwks_provider()
        payload = await verify_clerk_token(token, jwks_override=jwks_override)
        return payload.get("sub") or payload.get("user_id")

    return None


def invalidate_api_key_cache(clerk_user_id: str) -> None:
    """Remove a user's API key from the cache.

    Call this when an API key is rotated to ensure fresh data.

    Args:
        clerk_user_id: The Clerk user ID to invalidate.
    """
    if clerk_user_id in _api_key_cache:
        del _api_key_cache[clerk_user_id]
        logger.info("api_key_cache_invalidated", clerk_user_id=clerk_user_id)


class ApiKeyInjectionMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware that injects API keys into adapter-bound requests.

    Intercepts /v1/* and /adapter/* requests (which are destined for the adapter
    service), extracts the Clerk user ID from the incoming JWT, looks up the
    user's platform API key, and **rewrites** the Authorization header so the
    adapter sees a valid platform key rather than the Clerk JWT.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        """Rewrite Authorization header for adapter-bound requests."""
        path = request.url.path
        is_adapter_request = (
            path.startswith("/v1/") or
            path.startswith("/adapter/")
        )

        if is_adapter_request:
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Missing or invalid Authorization header"},
                )

            try:
                clerk_user_id = await _extract_clerk_user_id_from_request(request)
            except Exception as exc:
                detail = getattr(exc, "detail", "Invalid token")
                return JSONResponse(status_code=401, content={"detail": detail})

            if not clerk_user_id:
                return JSONResponse(status_code=401, content={"detail": "Invalid token"})

            try:
                db: AsyncSession = request.state.db  # type: ignore[attr-defined]
                api_key = await _get_api_key_for_clerk_user(db, clerk_user_id)

                if not api_key:
                    logger.warning(
                        "api_key_not_found",
                        clerk_user_id=clerk_user_id,
                        path=path,
                    )
                    return JSONResponse(status_code=401, content={"detail": "Invalid token"})

                # Rewrite the Authorization header so the adapter receives the
                # platform API key instead of the Clerk JWT. MutableHeaders
                # mutates the ASGI scope in-place — no request copy needed.
                mutable = MutableHeaders(scope=request.scope)
                mutable["Authorization"] = f"Bearer {api_key}"

                # Also preserve in state for logging / downstream access
                request.state.api_key = api_key  # type: ignore[attr-defined]
                logger.debug(
                    "api_key_injected",
                    clerk_user_id=clerk_user_id,
                    path=path,
                )
            except Exception as e:
                logger.error(
                    "api_key_injection_failed",
                    clerk_user_id=clerk_user_id,
                    error=str(e),
                    path=path,
                )
                return JSONResponse(status_code=401, content={"detail": "Invalid token"})

        response = await call_next(request)
        return response
