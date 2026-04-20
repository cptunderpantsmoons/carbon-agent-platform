"""Clerk-authenticated RAG gateway routes."""
from collections.abc import Mapping
from typing import Any

import httpx
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request
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


def _get_tenant_id_from_request(request: Request) -> str:
    """Extract tenant id from X-Tenant-Id header or fallback to fixed."""
    tenant_id = request.headers.get("X-Tenant-Id", "").strip()
    if tenant_id:
        return tenant_id
    return _get_fixed_tenant_id()


def build_scoped_rag_request(
    payload: dict[str, Any],
    principal: ClerkPrincipal,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    """Attach the tenant id and Clerk subject to a RAG payload."""
    if tenant_id is None:
        tenant_id = _get_fixed_tenant_id()
    return {
        "scope": {
            "tenant_id": tenant_id,
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
    query = scoped_request["payload"].get("query")
    if not query:
        raise HTTPException(status_code=400, detail="Missing query")

    return await _proxy_scoped_vector_store_request(
        path="/search",
        operation_name="search",
        scoped_request=scoped_request,
        upstream_payload={
            "query": query,
            "n_results": scoped_request["payload"].get("n_results", 10),
            "where_filter": scoped_request["scope"],
        },
    )


async def _proxy_scoped_vector_store_request(
    *,
    path: str,
    operation_name: str,
    scoped_request: dict[str, Any],
    upstream_payload: dict[str, Any],
) -> dict[str, Any]:
    """Proxy a scoped request to the vector-store service."""
    settings = get_settings()

    try:
        async with httpx.AsyncClient(base_url=settings.vector_store_url, timeout=10.0) as client:
            response = await client.post(path, json=upstream_payload)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail="Vector store service unavailable") from exc

    if response.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail=f"Vector store {operation_name} failed with status {response.status_code}",
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


def _ensure_active_principal(principal: ClerkPrincipal) -> None:
    """Reject suspended or inactive Carbon users from Contract Hub RAG access."""
    if principal.get("carbon_user_status") and principal["carbon_user_status"] != "active":
        raise HTTPException(status_code=403, detail="User account is not active")


def _build_scoped_where_filter(
    principal: ClerkPrincipal,
    extra_filter: Mapping[str, Any] | None = None,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    """Build the downstream where_filter for a scoped Contract Hub RAG request."""
    scoped_filter = build_scoped_rag_request({}, principal, tenant_id)["scope"]
    if extra_filter:
        scoped_filter.update(dict(extra_filter))
    return scoped_filter


@rag_router.post("/query")
@limiter.limit("60/minute", key_func=_get_clerk_rag_rate_limit_key)
async def query_rag(
    request: Request,
    payload: dict[str, Any],
    principal: ClerkPrincipal = Depends(verify_clerk_principal),
) -> dict[str, Any]:
    """Handle a scoped RAG query from Contract Hub."""
    _ensure_active_principal(principal)

    tenant_id = _get_tenant_id_from_request(request)
    scoped_request = build_scoped_rag_request(payload, principal, tenant_id)
    return await proxy_rag_request(scoped_request)



@rag_router.post("/ingest")
@limiter.limit("60/minute", key_func=_get_clerk_rag_rate_limit_key)
async def ingest_rag(
    request: Request,
    payload: dict[str, Any],
    principal: ClerkPrincipal = Depends(verify_clerk_principal),
) -> dict[str, Any]:
    """Ingest documents into the vector store with Clerk scoping."""
    _ensure_active_principal(principal)

    documents = payload.get("documents", [])
    if not documents:
        raise HTTPException(status_code=400, detail="Missing documents")

    # Merge scope into each document's metadata
    tenant_id = _get_tenant_id_from_request(request)

    scope = build_scoped_rag_request({}, principal, tenant_id)["scope"]
    metadatas = []
    texts = []
    ids = []
    for doc in documents:
        if not isinstance(doc, dict):
            raise HTTPException(status_code=400, detail="Each document must be a dict")
        text = doc.get("text")
        if not text:
            raise HTTPException(status_code=400, detail="Missing text in document")
        metadata = doc.get("metadata", {})
        # Merge scope
        metadata.update(scope)
        # Add document_id if present in doc
        if "document_id" in doc:
            metadata["document_id"] = doc["document_id"]
        metadatas.append(metadata)
        texts.append(text)
        # Generate ID if not provided
        ids.append(doc.get("id", str(uuid.uuid4())))

    upstream_payload = {
        "documents": [{"text": text, "metadata": metadata} for text, metadata in zip(texts, metadatas)],
        "ids": ids,
        "batch_size": payload.get("batch_size", 500),
    }

    scoped_request = build_scoped_rag_request(payload, principal, tenant_id)
    return await _proxy_scoped_vector_store_request(
        path="/add",
        operation_name="add",
        scoped_request=scoped_request,
        upstream_payload=upstream_payload,
    )

@rag_router.delete("/documents/{document_id}")
@limiter.limit("60/minute", key_func=_get_clerk_rag_rate_limit_key)
async def delete_rag_documents(
    request: Request,
    document_id: str,
    principal: ClerkPrincipal = Depends(verify_clerk_principal),
) -> dict[str, Any]:
    """Delete only the caller's scoped RAG documents."""
    _ensure_active_principal(principal)

    tenant_id = _get_tenant_id_from_request(request)
    if not document_id:
        raise HTTPException(status_code=400, detail="Missing document_id")

    payload = {"document_id": document_id}
    scoped_request = build_scoped_rag_request(payload, principal, tenant_id)
    return await _proxy_scoped_vector_store_request(
        path="/delete",
        operation_name="delete",
        scoped_request=scoped_request,
        upstream_payload={
            "where_filter": _build_scoped_where_filter(
                principal,
                {"document_id": document_id},
            ),
        },
    )


@rag_router.get("/stats")
@limiter.limit("60/minute", key_func=_get_clerk_rag_rate_limit_key)
async def rag_stats(
    request: Request,
    principal: ClerkPrincipal = Depends(verify_clerk_principal),
) -> dict[str, Any]:
    """Return stats for the caller's scoped RAG documents."""
    _ensure_active_principal(principal)

    tenant_id = _get_tenant_id_from_request(request)
    payload: dict[str, Any] = {}
    scoped_request = build_scoped_rag_request(payload, principal, tenant_id)
    return await _proxy_scoped_vector_store_request(
        path="/stats",
        operation_name="stats",
        scoped_request=scoped_request,
        upstream_payload={
            "where_filter": _build_scoped_where_filter(principal, None, tenant_id),
        },
    )
