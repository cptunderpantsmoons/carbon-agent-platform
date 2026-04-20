"""Authentication routes for Clerk-based API key retrieval.

Provides the /api/v1/auth/get-api-key endpoint used by the Open WebUI
clerk-integration.js to fetch the user's API key after Clerk authentication.
"""

from fastapi import APIRouter, Depends, HTTPException, Header, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clerk_auth import get_clerk_jwks_for_verification, verify_clerk_token
from app.models import User, UserStatus
from app.config import get_settings
from app.database import get_session
from app.rate_limit import limiter, _get_user_id_or_ip

import structlog

logger = structlog.get_logger(__name__)

auth_router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@auth_router.get("/get-api-key")
@limiter.limit("60/minute", key_func=_get_user_id_or_ip)
async def get_api_key(
    request: Request,
    authorization: str = Header(default=""),
    db: AsyncSession = Depends(get_session),
    jwks_override: dict | None = Depends(get_clerk_jwks_for_verification),
):
    """Retrieve the user's API key using their Clerk session token.

    Called by clerk-integration.js after Clerk authenticates the user.
    Extracts the Clerk user ID from the JWT, looks up the user,
    and returns their platform API key.

    Returns:
        dict with api_key field.

    Raises:
        HTTPException: If authentication fails or user not found.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401, detail="Missing or invalid Authorization header"
        )

    token = authorization[7:]

    try:
        payload = await verify_clerk_token(token, jwks_override=jwks_override)
        clerk_user_id = payload.get("sub") or payload.get("user_id")
    except HTTPException as exc:
        raise exc

    if not clerk_user_id:
        raise HTTPException(status_code=401, detail="Invalid token: missing user ID")

    # Look up the user's API key
    result = await db.execute(select(User).where(User.clerk_user_id == clerk_user_id))
    user = result.scalar_one_or_none()

    if not user:
        # Try email fallback from token
        email = payload.get("email") or payload.get("email_address")
        if email:
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()
            if user and not user.clerk_user_id:
                user.clerk_user_id = clerk_user_id
                await db.commit()

    if not user:
        raise HTTPException(status_code=404, detail="User not found in platform")

    if user.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=403, detail="User account is not active")

    logger.info(
        "api_key_retrieved_via_clerk", user_id=user.id, clerk_user_id=clerk_user_id
    )

    return {"api_key": user.api_key, "user_id": user.id}


@auth_router.get("/clerk-status")
@limiter.limit("60/minute", key_func=_get_user_id_or_ip)
async def clerk_status(request: Request):
    """Check if Clerk authentication is configured and available.

    Returns:
        dict with clerk_enabled status.
    """
    settings = get_settings()
    return {
        "clerk_enabled": bool(settings.clerk_webhook_secret),
        "service": "orchestrator",
    }
