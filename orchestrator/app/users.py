"""User-facing API endpoints for account and session management."""
import uuid
import secrets
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_session
from app.models import User, AuditLog, UserStatus
from app.schemas import UserResponse, UserUpdate, ApiKeyRotateResponse
from app.session_manager import get_session_manager
from app.api_key_injection import invalidate_api_key_cache
from app.rate_limit import limiter, _get_user_id_or_ip
from typing import Optional

import structlog

logger = structlog.get_logger()
user_router = APIRouter(prefix="/user", tags=["user"])


async def verify_user_api_key(
    authorization: Optional[str] = Header(default=None),
    db: AsyncSession = Depends(get_session),
) -> User:
    """Verify user API key and return authenticated user.

    Args:
        authorization: Authorization header (Bearer token)
        db: Database session

    Returns:
        Authenticated user

    Raises:
        HTTPException: If authentication fails
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header format")

    api_key = authorization[7:]  # Remove "Bearer " prefix

    result = await db.execute(select(User).where(User.api_key == api_key))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid API key")

    if user.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=403, detail="User account is not active")

    return user


@user_router.get("/me", response_model=UserResponse)
@limiter.limit("60/minute", key_func=_get_user_id_or_ip)
async def get_my_profile(
    request: Request,
    user: User = Depends(verify_user_api_key),
):
    """Get current authenticated user's profile."""
    return user


@user_router.patch("/me", response_model=UserResponse)
@limiter.limit("60/minute", key_func=_get_user_id_or_ip)
async def update_my_profile(
    request: Request,
    data: UserUpdate,
    user: User = Depends(verify_user_api_key),
    db: AsyncSession = Depends(get_session),
):
    """Update current user's profile."""
    # Only allow certain fields to be updated by users
    if data.display_name is not None:
        user.display_name = data.display_name
    if data.config is not None:
        user.config = data.config

    log = AuditLog(
        id=str(uuid.uuid4()),
        user_id=user.id,
        action="user.updated",
        details={"field": "profile_update"},
        performed_by=user.email,
    )
    db.add(log)
    await db.commit()
    await db.refresh(user)
    return user


@user_router.get("/me/session")
@limiter.limit("60/minute", key_func=_get_user_id_or_ip)
async def get_my_session_info(
    request: Request,
    user: User = Depends(verify_user_api_key),
):
    """Get current user's session information."""
    session_manager = get_session_manager()
    session_info = await session_manager.get_session_info(user.id)

    if not session_info:
        return {"active": False}

    return {
        "active": True,
        "last_activity": session_info["last_activity"],
        "idle_seconds": session_info["idle_seconds"],
        "timeout_seconds": session_info["timeout_seconds"],
    }


@user_router.post("/me/session/refresh")
@limiter.limit("60/minute", key_func=_get_user_id_or_ip)
async def refresh_session(
    request: Request,
    user: User = Depends(verify_user_api_key),
    db: AsyncSession = Depends(get_session),
):
    """Refresh user session to prevent timeout."""
    session_manager = get_session_manager()
    await session_manager.record_activity(user.id)

    return {"status": "refreshed"}


@user_router.post("/me/service/ensure")
@limiter.limit("60/minute", key_func=_get_user_id_or_ip)
async def ensure_my_service(
    request: Request,
    user: User = Depends(verify_user_api_key),
    db: AsyncSession = Depends(get_session),
):
    """Ensure user has an active Railway service (spin up if needed)."""
    session_manager = get_session_manager()
    was_created, _ = await session_manager.ensure_user_service(db, user.id)
    await db.commit()

    if was_created:
        return {"status": "created", "message": "Service spun up successfully"}
    return {"status": "existing", "message": "Service already active"}


@user_router.post("/me/service/spin-down")
@limiter.limit("60/minute", key_func=_get_user_id_or_ip)
async def spin_down_my_service(
    request: Request,
    user: User = Depends(verify_user_api_key),
    db: AsyncSession = Depends(get_session),
):
    """Spin down user's Railway service."""
    session_manager = get_session_manager()
    result = await session_manager.spin_down_user_service(db, user.id)
    await db.commit()

    if result:
        return {"status": "spun_down", "message": "Service spun down successfully"}
    return {"status": "not_found", "message": "No active service to spin down"}


@user_router.get("/me/service/status")
@limiter.limit("60/minute", key_func=_get_user_id_or_ip)
async def get_my_service_status(
    request: Request,
    user: User = Depends(verify_user_api_key),
    db: AsyncSession = Depends(get_session),
):
    """Get current user's Railway service status."""
    session_manager = get_session_manager()
    status = await session_manager.get_service_status(db, user.id)

    if not status:
        return {"active": False}

    return {
        "active": True,
        "service_id": status["service_id"],
        "volume_id": status["volume_id"],
        "status": status.get("status"),
        "updated_at": status.get("updated_at"),
        "instances": status.get("instances", []),
    }


@user_router.post("/me/api-key/rotate", response_model=ApiKeyRotateResponse)
@limiter.limit("60/minute", key_func=_get_user_id_or_ip)
async def rotate_my_api_key(
    request: Request,
    user: User = Depends(verify_user_api_key),
    db: AsyncSession = Depends(get_session),
):
    """Rotate user's API key."""
    old_key = user.api_key
    new_key = f"sk-{secrets.token_hex(24)}"

    user.api_key = new_key
    if user.clerk_user_id:
        invalidate_api_key_cache(user.clerk_user_id)

    log = AuditLog(
        id=str(uuid.uuid4()),
        user_id=user.id,
        action="user.api_key_rotated",
        details={"old_key_last_4": old_key[-4:] if old_key else None},
        performed_by=user.email,
    )
    db.add(log)
    await db.commit()
    await db.refresh(user)

    return {
        "status": "rotated",
        "new_api_key": new_key,
        "message": "API key rotated successfully",
    }
