"""Admin API endpoints for managing users."""

import uuid
import secrets
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_session
from app.models import User, AuditLog, UserStatus
from app.schemas import (
    UserCreate,
    UserResponse,
    UserUpdate,
    UserWithApiKeyResponse,
    AdminCommand,
    AdminResponse,
    PlatformHealth,
)
from app.session_manager import get_session_manager
from app.clerk_auth import verify_clerk_token, get_clerk_jwks_for_verification

import structlog

logger = structlog.get_logger()
admin_router = APIRouter(prefix="/admin", tags=["admin"])


async def verify_admin_jwt(
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_session),
    jwks_override: dict | None = Depends(get_clerk_jwks_for_verification),
) -> User:
    """Verify Clerk JWT and ensure the user has the admin role.

    Extracts the Bearer token from the Authorization header, validates the JWT,
    looks up the user, and verifies they have ``role = "admin"`` in their
    Clerk ``public_metadata``.

    Args:
        authorization: Authorization header containing the Bearer token.
        db: Injected database session.
        jwks_override: Optional JWKS payload injected by tests.

    Returns:
        Authenticated admin User object.

    Raises:
        HTTPException: If authentication fails or the user is not an admin.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401, detail="Invalid Authorization header format"
        )

    token = authorization[7:]

    payload = await verify_clerk_token(token, jwks_override=jwks_override)

    clerk_user_id = payload.get("sub") or payload.get("user_id")
    if not clerk_user_id:
        raise HTTPException(status_code=401, detail="Invalid token: missing user ID")

    # Check for admin role in Clerk public_metadata
    public_metadata = payload.get("public_metadata", {})
    user_role = (
        public_metadata.get("role") if isinstance(public_metadata, dict) else None
    )

    if user_role != "admin":
        logger.warning(
            "admin_access_denied_non_admin_role",
            clerk_user_id=clerk_user_id,
            role=user_role,
        )
        raise HTTPException(status_code=403, detail="Admin access required")

    # Look up user in database
    result = await db.execute(select(User).where(User.clerk_user_id == clerk_user_id))
    user = result.scalar_one_or_none()

    if not user:
        # Email fallback for users created before Clerk sign-up
        email = payload.get("email") or payload.get("email_address")
        if email:
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()
            if user and not user.clerk_user_id:
                user.clerk_user_id = clerk_user_id
                await db.commit()

    if not user:
        raise HTTPException(status_code=401, detail="User not found in platform")

    if user.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=403, detail="User account is not active")

    logger.info("admin_access_granted", user_id=user.id, clerk_user_id=clerk_user_id)
    return user


@admin_router.get("/health", response_model=PlatformHealth)
async def platform_health(
    db: AsyncSession = Depends(get_session),
    _: User = Depends(verify_admin_jwt),
):
    """Get platform-wide health metrics."""
    total_users = await db.scalar(select(func.count(User.id)))
    active_users = await db.scalar(
        select(func.count(User.id)).where(User.status == UserStatus.ACTIVE)
    )

    return PlatformHealth(
        total_users=total_users or 0,
        total_volumes=active_users or 0,
    )


@admin_router.post("/users", response_model=UserWithApiKeyResponse)
async def create_user(
    data: UserCreate,
    db: AsyncSession = Depends(get_session),
    _: User = Depends(verify_admin_jwt),
):
    """Create a new user. Returns api_key on creation only."""
    user = User(
        id=str(uuid.uuid4()),
        email=data.email,
        display_name=data.display_name,
        api_key=f"sk-{secrets.token_hex(24)}",
        status=UserStatus.ACTIVE,
        config=data.config,
    )
    db.add(user)

    log = AuditLog(
        id=str(uuid.uuid4()),
        user_id=user.id,
        action="user.created",
        details={"email": data.email},
        performed_by="admin_agent",
    )
    db.add(log)
    await db.commit()
    await db.refresh(user)

    logger.info("user_created", user_id=user.id, email=data.email)
    return user


@admin_router.get("/users", response_model=list[UserResponse])
async def list_users(
    db: AsyncSession = Depends(get_session),
    _: User = Depends(verify_admin_jwt),
):
    """List all users."""
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return result.scalars().all()


@admin_router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_session),
    _: User = Depends(verify_admin_jwt),
):
    """Get a specific user."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@admin_router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    data: UserUpdate,
    db: AsyncSession = Depends(get_session),
    _: User = Depends(verify_admin_jwt),
):
    """Update a user."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if data.display_name is not None:
        user.display_name = data.display_name
    if data.status is not None:
        user.status = data.status
    if data.config is not None:
        user.config = data.config

    log = AuditLog(
        id=str(uuid.uuid4()),
        user_id=user_id,
        action="user.updated",
        details=data.model_dump(exclude_none=True),
        performed_by="admin_agent",
    )
    db.add(log)
    await db.commit()
    await db.refresh(user)
    return user


@admin_router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    db: AsyncSession = Depends(get_session),
    _: User = Depends(verify_admin_jwt),
):
    """Delete a user and spin down their Railway service."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Spin down Docker container before removing the DB record
    if user.status == UserStatus.ACTIVE:
        try:
            session_manager = get_session_manager()
            await session_manager.spin_down_user_service(db, user_id)
        except Exception as e:
            logger.error(
                "admin_delete_service_spindown_failed", user_id=user_id, error=str(e)
            )
            # Continue with deletion even if spindown fails; log the orphaned service

    log = AuditLog(
        id=str(uuid.uuid4()),
        user_id=user_id,
        action="user.deleted",
        details={"email": user.email},
        performed_by="admin_agent",
    )
    db.add(log)
    await db.flush()

    await db.delete(user)
    await db.commit()
    return {"status": "deleted", "user_id": user_id}


@admin_router.post("/users/{user_id}/spin-down")
async def admin_spin_down_user_service(
    user_id: str,
    db: AsyncSession = Depends(get_session),
    _: User = Depends(verify_admin_jwt),
):
    """Admin: spin down a user's Docker container."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.status != UserStatus.ACTIVE:
        return {"status": "no_service", "message": "User has no active service"}

    session_manager = get_session_manager()
    spun_down = await session_manager.spin_down_user_service(db, user_id)

    log = AuditLog(
        id=str(uuid.uuid4()),
        user_id=user_id,
        action="admin.service_spun_down",
        details={"user_id": user_id, "previous_status": "active"},
        performed_by="admin_agent",
    )
    db.add(log)
    await db.commit()

    return {"status": "spun_down" if spun_down else "no_service", "user_id": user_id}


@admin_router.post("/command", response_model=AdminResponse)
async def admin_command(
    command: AdminCommand,
    _: User = Depends(verify_admin_jwt),
):
    """Natural language command interface."""
    return AdminResponse(
        status="received",
        message=f"Command '{command.command}' acknowledged. Use specific endpoints for execution.",
        data=command.context,
    )


@admin_router.get("/sessions")
async def list_active_sessions(
    db: AsyncSession = Depends(get_session),
    _: User = Depends(verify_admin_jwt),
):
    """List all users with active Docker containers."""
    result = await db.execute(
        select(User)
        .where(User.status == UserStatus.ACTIVE)
        .order_by(User.updated_at.desc())
    )
    active_users = result.scalars().all()

    return {
        "active_services": len(active_users),
        "sessions": [
            {
                "user_id": u.id,
                "email": u.email,
                "display_name": u.display_name,
                "status": u.status.value,
                "updated_at": u.updated_at.isoformat() if u.updated_at else None,
            }
            for u in active_users
        ],
    }


@admin_router.get("/metrics")
async def platform_metrics(
    db: AsyncSession = Depends(get_session),
    _: User = Depends(verify_admin_jwt),
):
    """Get platform metrics for the admin dashboard."""
    total_users = await db.scalar(select(func.count(User.id)))
    active_users = await db.scalar(
        select(func.count(User.id)).where(User.status == UserStatus.ACTIVE)
    )
    suspended_users = await db.scalar(
        select(func.count(User.id)).where(User.status == UserStatus.SUSPENDED)
    )
    pending_users = await db.scalar(
        select(func.count(User.id)).where(User.status == UserStatus.PENDING)
    )
    active_services = await db.scalar(
        select(func.count(User.id)).where(User.status == UserStatus.ACTIVE)
    )

    return {
        "total_users": total_users or 0,
        "active_users": active_users or 0,
        "suspended_users": suspended_users or 0,
        "pending_users": pending_users or 0,
        "active_services": active_services or 0,
    }
