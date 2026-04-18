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
    """Return the Clerk JWKS endpoint URL."""
    return "https://api.clerk.com/v1/jwks"


def _jwk_to_pem(jwk: Mapping[str, object]) -> str:
    """Convert a JWK dict into a PEM-encoded public key string."""
    public_key = jwt.algorithms.RSAAlgorithm.from_jwk(dict(jwk))
    if isinstance(public_key, str):
        return public_key
    return public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")


async def _fetch_clerk_public_key(key_id: str | None = None) -> str:
    """Fetch Clerk's public key for JWT verification.

    Uses the configured static key if present; otherwise fetches from the
    Clerk JWKS endpoint and caches the result for _PUBLIC_KEY_CACHE_TTL seconds.

    Args:
        key_id: Optional key ID (kid) to select a specific key from JWKS.

    Returns:
        PEM-encoded public key string.

    Raises:
        HTTPException: If unable to fetch or locate the public key.
    """
    settings = get_settings()
    if settings.clerk_jwt_public_key:
        return settings.clerk_jwt_public_key

    cache_key = key_id or "default"
    if cache_key in _clerk_public_keys:
        key, expires_at = _clerk_public_keys[cache_key]
        if time.time() < expires_at:
            return key

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(_get_clerk_jwks_url(), timeout=10.0)
            response.raise_for_status()
            jwks = response.json()

        for jwk in jwks.get("keys", []):
            if key_id is None or jwk.get("kid") == key_id:
                pem_key = _jwk_to_pem(jwk)
                _clerk_public_keys[cache_key] = (pem_key, time.time() + _PUBLIC_KEY_CACHE_TTL)
                return pem_key

        detail = "Invalid token: unknown key ID" if key_id else "Invalid token"
        raise HTTPException(status_code=401, detail=detail)

    except httpx.HTTPError as e:
        logger.error("clerk_jwks_fetch_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch Clerk public key")


def _resolve_test_jwks_key(jwks_override: Mapping[str, object], key_id: str | None) -> str:
    """Resolve a PEM key from a supplied JWKS payload (used in tests)."""
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
    """Decode and validate a Clerk JWT token with RS256 signature verification.

    When CLERK_JWT_ISSUER is configured the issuer claim is verified.
    When it is empty, issuer verification is skipped (backward-compatible default;
    set CLERK_JWT_ISSUER in production for full security).

    Args:
        token: Raw JWT string.
        jwks_override: Optional JWKS dict injected by tests.

    Returns:
        Decoded payload dict.

    Raises:
        HTTPException: On any validation failure.
    """
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

    # Enable issuer verification when the issuer URL is explicitly configured.
    verify_iss = bool(settings.clerk_jwt_issuer)
    decode_kwargs: dict = dict(
        algorithms=["RS256"],
        options={
            "verify_aud": False,
            "verify_exp": True,
            "verify_nbf": True,
            "verify_iss": verify_iss,
        },
    )
    if verify_iss:
        decode_kwargs["issuer"] = settings.clerk_jwt_issuer

    try:
        return jwt.decode(token, public_key, **decode_kwargs)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidIssuerError:
        logger.warning("clerk_jwt_invalid_issuer")
        raise HTTPException(status_code=401, detail="Invalid token: issuer mismatch")
    except jwt.InvalidTokenError as e:
        logger.warning("clerk_jwt_invalid", error=str(e))
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")


async def verify_clerk_jwt(
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_session),
    jwks_override: dict | None = Depends(get_clerk_jwks_for_verification),
) -> User:
    """FastAPI dependency: verify Clerk JWT and return the authenticated User.

    Extracts the Bearer token from the Authorization header, validates the JWT,
    then looks up the user by clerk_user_id (with email fallback for linking).

    Args:
        authorization: Authorization header containing the Bearer token.
        db: Injected database session.
        jwks_override: Optional JWKS payload injected by tests.

    Returns:
        Authenticated and active User object.

    Raises:
        HTTPException: If authentication or authorisation fails.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header format")

    token = authorization[7:]

    payload = await verify_clerk_token(token, jwks_override=jwks_override)

    clerk_user_id = payload.get("sub") or payload.get("user_id")
    if not clerk_user_id:
        raise HTTPException(status_code=401, detail="Invalid token: missing user ID")

    result = await db.execute(select(User).where(User.clerk_user_id == clerk_user_id))
    user = result.scalar_one_or_none()

    if not user:
        # Email fallback: links tokens for users provisioned before Clerk signup
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

    return user
