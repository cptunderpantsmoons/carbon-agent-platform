"""Clerk-authenticated RAG gateway routes."""
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

import app.clerk_auth as clerk_auth
from app.clerk_auth import ClerkPrincipal, verify_clerk_principal
from app.config import get_settings
from app.rate_limit import limiter


rag_router = APIRouter(prefix="/api/v1/rag", tags=["rag"])


def _get_fixed_tenant_id() -> str:
    """Return the tenant id used to scope all RAG requests."""
    tenant_id = get_settings().rag_fixed_tenant_id.strip()
    if not tenant_id:
        raise HTTPException(status_code=500, detail="RAG tenant id is not configured")
    return tenant_id


def build_scoped_rag_request(
    payload: dict[str, Any],
    principal: ClerkPrincipal,
) -> dict[str, Any]:
    """Attach the fixed tenant id and Clerk subject to a RAG payload."""
    return {
        "scope": {
            "tenant_id": _get_fixed_tenant_id(),
            "clerk_user_id": principal["clerk_user_id"],
        },
        "payload": payload,
    }


class ClerkRAGIdentityMiddleware(BaseHTTPMiddleware):
    """Populate a verified Clerk user id for RAG rate limiting."""

    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/api/v1/rag/"):
            authorization = request.headers.get("Authorization", "")
            if authorization.startswith("Bearer "):
                token = authorization[7:]
                try:
                    jwks_override = clerk_auth.get_clerk_jwks_for_verification()
                    payload = await clerk_auth.verify_clerk_token(
                        token,
                        jwks_override=jwks_override,
                    )
                except HTTPException:
                    pass
                else:
                    clerk_user_id = payload.get("sub") or payload.get("user_id")
                    if clerk_user_id:
                        request.state.user_id = str(clerk_user_id)

        return await call_next(request)


def _get_clerk_rag_rate_limit_key(request: Request) -> str:
    """Return a stable rate-limit key from verified auth state or client IP."""
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return f"user:{user_id}"

    return get_remote_address(request)


async def proxy_rag_request(scoped_request: dict[str, Any]) -> dict[str, Any]:
    """Proxy a scoped RAG query to the vector-store service."""
    settings = get_settings()
    query = scoped_request["payload"].get("query")
    if not query:
        raise HTTPException(status_code=400, detail="Missing query")

    upstream_payload = {
        "query": query,
        "n_results": scoped_request["payload"].get("n_results", 10),
        "where_filter": scoped_request["scope"],
    }

    try:
        async with httpx.AsyncClient(base_url=settings.vector_store_url, timeout=10.0) as client:
            response = await client.post("/search", json=upstream_payload)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail="Vector store service unavailable") from exc

    if response.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail=f"Vector store search failed with status {response.status_code}",
        )

    try:
        downstream_result = response.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="Vector store returned invalid JSON") from exc

    return {
        "scope": scoped_request["scope"],
        "payload": scoped_request["payload"],
        "result": downstream_result,
    }


@rag_router.post("/query")
@limiter.limit("60/minute", key_func=_get_clerk_rag_rate_limit_key)
async def query_rag(
    request: Request,
    payload: dict[str, Any],
    principal: ClerkPrincipal = Depends(verify_clerk_principal),
) -> dict[str, Any]:
    """Handle a scoped RAG query from Contract Hub."""
    if principal.get("carbon_user_status") and principal["carbon_user_status"] != "active":
        return JSONResponse(status_code=403, content={"detail": "User account is not active"})

    scoped_request = build_scoped_rag_request(payload, principal)
    return await proxy_rag_request(scoped_request)
