"""Clerk JWT authentication middleware."""
import time
from collections.abc import Mapping

import httpx
import jwt
from cryptography.hazmat.primitives import serialization
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_session
from app.models import User, UserStatus

import structlog

logger = structlog.get_logger(__name__)

# Cache for Clerk public keys with expiry
_clerk_public_keys: dict[str, tuple[str, float]] = {}
_PUBLIC_KEY_CACHE_TTL = 3600  # 1 hour


def get_clerk_jwks_for_verification() -> dict | None:
    """FastAPI dependency hook for deterministic JWT verification in tests."""
    return None


def _get_clerk_jwks_url() -> str:
    """Get the JWKS URL for Clerk."""
    # The publishable key usually starts with pk_test_ or pk_live_
    # We can derive the frontend API URL from it
    return "https://api.clerk.com/v1/jwks"


def _jwk_to_pem(jwk: Mapping[str, object]) -> str:
    """Convert a JWK dict into PEM public key."""
    public_key = jwt.algorithms.RSAAlgorithm.from_jwk(dict(jwk))
    if isinstance(public_key, str):
        return public_key
    return public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")


async def _fetch_clerk_public_key(key_id: str | None = None) -> str:
    """Fetch Clerk's public key for JWT verification.

    Fetches from Clerk's JWKS endpoint and caches the result.

    Args:
        key_id: Optional key ID to filter for a specific key.

    Returns:
        PEM-encoded public key string.

    Raises:
        HTTPException: If unable to fetch public key.
    """
    # If a static public key is configured, use it directly
    settings = get_settings()
    if settings.clerk_jwt_public_key:
        return settings.clerk_jwt_public_key

    # Check cache
    cache_key = key_id or "default"
    if cache_key in _clerk_public_keys:
        key, expires_at = _clerk_public_keys[cache_key]
        if time.time() < expires_at:
            return key

    # Fetch from Clerk API
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(_get_clerk_jwks_url(), timeout=10.0)
            response.raise_for_status()
            jwks = response.json()

        # Find the matching key
        for jwk in jwks.get("keys", []):
            if key_id is None or jwk.get("kid") == key_id:
                pem_key = _jwk_to_pem(jwk)

                # Cache the key
                _clerk_public_keys[cache_key] = (pem_key, time.time() + _PUBLIC_KEY_CACHE_TTL)
                return pem_key

        if key_id is not None:
            raise HTTPException(status_code=401, detail="Invalid token: unknown key ID")
        raise HTTPException(status_code=401, detail="Invalid token")

    except httpx.HTTPError as e:
        logger.error("clerk_jwks_fetch_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch Clerk public key")


def _resolve_test_jwks_key(jwks_override: Mapping[str, object], key_id: str | None) -> str:
    """Resolve a PEM key from a supplied JWKS payload."""
    keys = jwks_override.get("keys", [])
    if not isinstance(keys, list):
        raise HTTPException(status_code=500, detail="Invalid JWKS override")

    for jwk in keys:
        if not isinstance(jwk, Mapping):
            continue
        if key_id is None or jwk.get("kid") == key_id:
            return _jwk_to_pem(jwk)

    raise HTTPException(status_code=401, detail="Invalid token: unknown key ID")


async def verify_clerk_token(
    token: str,
    jwks_override: Mapping[str, object] | None = None,
) -> dict:
    """Decode and validate a Clerk JWT token with RS256 signature verification."""
    try:
        unverified_headers = jwt.get_unverified_header(token)
        key_id = unverified_headers.get("kid")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token format")

    settings = get_settings()
    if settings.clerk_jwt_public_key:
        public_key = settings.clerk_jwt_public_key
    elif jwks_override is not None:
        public_key = _resolve_test_jwks_key(jwks_override, key_id)
    else:
        public_key = await _fetch_clerk_public_key(key_id)

    try:
        return jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            options={
                "verify_aud": False,
                "verify_exp": True,
                "verify_nbf": True,
                "verify_iss": False,
            },
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError as e:
        logger.warning("clerk_jwt_invalid", error=str(e))
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")


def _decode_clerk_jwt(token: str) -> dict:
    """Decode and validate a Clerk JWT token.

    Args:
        token: The JWT token string.

    Returns:
        Decoded token payload.

    Raises:
        HTTPException: If token is invalid.
    """
    try:
        jwt.get_unverified_header(token)
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token format")

    settings = get_settings()
    if not settings.clerk_jwt_public_key:
        raise HTTPException(status_code=500, detail="Unable to verify token")

    try:
        return jwt.decode(
            token,
            settings.clerk_jwt_public_key,
            algorithms=["RS256"],
            options={
                "verify_aud": False,
                "verify_exp": True,
                "verify_nbf": True,
                "verify_iss": False,
            },
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError as e:
        logger.warning("clerk_jwt_invalid", error=str(e))
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")


async def verify_clerk_jwt(
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_session),
    jwks_override: dict | None = Depends(get_clerk_jwks_for_verification),
) -> User:
    """FastAPI dependency to verify Clerk JWT and return the authenticated user.

    Extracts Bearer token from Authorization header, validates JWT,
    looks up user by clerk_user_id, and returns the User object.

    Args:
        authorization: Authorization header with Bearer token.
        db: Database session.

    Returns:
        Authenticated User object.

    Raises:
        HTTPException: If authentication fails.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header format")

    token = authorization[7:]  # Remove "Bearer " prefix

    # Decode and validate the JWT
    payload = await verify_clerk_token(token, jwks_override=jwks_override)

    # Extract Clerk user ID from payload
    clerk_user_id = payload.get("sub") or payload.get("user_id")
    if not clerk_user_id:
        raise HTTPException(status_code=401, detail="Invalid token: missing user ID")

    # Look up the user in the database
    result = await db.execute(
        select(User).where(User.clerk_user_id == clerk_user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        # Fallback: try to find by email from token
        email = payload.get("email") or payload.get("email_address")
        if email:
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()

            # Link the Clerk ID if we found the user by email
            if user and not user.clerk_user_id:
                user.clerk_user_id = clerk_user_id
                await db.commit()

    if not user:
        raise HTTPException(status_code=401, detail="User not found in platform")

    if user.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=403, detail="User account is not active")

    return user


def get_clerk_user_id(authorization: str = Header(default="")) -> str | None:
    """Extract Clerk user ID from Bearer token without full validation.

    This is a lightweight helper for middleware that just needs the user ID.
    Does NOT validate the token signature - use verify_clerk_jwt for auth.

    Args:
        authorization: Authorization header with Bearer token.

    Returns:
        Clerk user ID or None.
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None

    token = authorization[7:]

    try:
        payload = _decode_clerk_jwt(token)
        return payload.get("sub") or payload.get("user_id")
    except HTTPException:
        return None
