"""Authentication middleware and utilities for adapter."""
from fastapi import HTTPException, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
import structlog

from app.database import async_session_factory
from app.models import User, UserStatus

logger = structlog.get_logger()


async def get_db():
    """Get database session for dependency injection."""
    async with async_session_factory() as session:
        yield session


async def verify_api_key(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Verify API key and return authenticated user.

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

    # Extract token from "Bearer {token}" format
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header format")

    api_key = authorization[7:]  # Remove "Bearer " prefix

    # Look up user by API key
    result = await db.execute(
        select(User).where(User.api_key == api_key)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid API key")

    if user.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=403, detail="User account is not active")

    logger.info("authenticated_user", user_id=user.id, email=user.email)
    return user
