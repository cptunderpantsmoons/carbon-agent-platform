"""Admin API endpoints for managing users."""
import hmac
import uuid
import secrets
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_session
from app.models import User, AuditLog, UserStatus
from app.schemas import (
    UserCreate, UserResponse, UserUpdate,
    AdminCommand, AdminResponse,
    PlatformHealth,
)
from app.config import get_settings

import structlog

logger = structlog.get_logger()
admin_router = APIRouter(prefix="/admin", tags=["admin"])


async def verify_admin_key(x_admin_key: str = Header(...)) -> str:
    settings = get_settings()
    if not hmac.compare_digest(x_admin_key, settings.admin_agent_api_key):
        raise HTTPException(status_code=403, detail="Invalid admin key")
    return x_admin_key


@admin_router.get("/health", response_model=PlatformHealth)
async def platform_health(
    db: AsyncSession = Depends(get_session),
    _: str = Depends(verify_admin_key),
):
    """Get platform-wide health metrics."""
    total_users = await db.scalar(select(func.count(User.id)))
    total_volumes = await db.scalar(
        select(func.count(User.volume_id)).where(User.volume_id.isnot(None))
    )

    return PlatformHealth(
        total_users=total_users or 0,
        total_volumes=total_volumes or 0,
    )


@admin_router.post("/users", response_model=UserResponse)
async def create_user(
    data: UserCreate,
    db: AsyncSession = Depends(get_session),
    _: str = Depends(verify_admin_key),
):
    """Create a new user."""
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
    _: str = Depends(verify_admin_key),
):
    """List all users."""
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return result.scalars().all()


@admin_router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_session),
    _: str = Depends(verify_admin_key),
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
    _: str = Depends(verify_admin_key),
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
    _: str = Depends(verify_admin_key),
):
    """Delete a user."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

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


@admin_router.post("/command", response_model=AdminResponse)
async def admin_command(
    command: AdminCommand,
    _: str = Depends(verify_admin_key),
):
    """Natural language command interface."""
    return AdminResponse(
        status="received",
        message=f"Command '{command.command}' acknowledged. Use specific endpoints for execution.",
        data=command.context,
    )
