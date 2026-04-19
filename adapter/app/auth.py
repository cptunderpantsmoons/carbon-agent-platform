"""Authentication middleware and utilities for adapter."""
from fastapi import HTTPException, Depends, Header
from typing import Optional
from datetime import datetime, timezone
import structlog
from app.models import User, UserStatus

logger = structlog.get_logger()

async def get_db():
    """Get database session for dependency injection."""
    # Return a dummy async generator that yields None
    yield None

async def verify_api_key(
    authorization: Optional[str] = Header(None),
    db = None,
) -> User:
    """Verify API key and return authenticated user.

    Args:
        authorization: Authorization header (Bearer token)
        db: Database session (ignored)

    Returns:
        Authenticated user (dummy)

    Raises:
        HTTPException: If authentication fails
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    # Extract token from "Bearer {token}" format
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header format")

    api_key = authorization[7:]  # Remove "Bearer " prefix

    # Accept any non-empty API key for development
    if not api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Return a dummy user
    logger.info("authenticated_user", user_id="dummy", email="dummy@example.com")
    return User(
        id="dummy",
        email="dummy@example.com",
        display_name="Development User",
        api_key=api_key,
        status=UserStatus.ACTIVE,
        clerk_user_id=None,
        config=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
