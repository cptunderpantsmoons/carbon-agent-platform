"""Tests for the Clerk-authenticated RAG gateway."""

from datetime import datetime, timedelta, timezone
import json
from unittest.mock import patch

import jwt
import httpx
import pytest
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import ASGITransport, AsyncClient

from app.clerk_auth import get_clerk_jwks_for_verification
from app.config import get_settings
from app.database import get_session
from app.main import app
from app.main import _validate_production_config
from app.models import User, UserStatus
from app.rate_limit import limiter


def _generate_rsa_keypair() -> tuple[rsa.RSAPrivateKey, dict]:
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )
    public_jwk = json.loads(
        jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key())
    )
    public_jwk.update({"kid": "rag-test-kid", "alg": "RS256", "use": "sig"})
    return private_key, {"keys": [public_jwk]}


def _make_clerk_token(
    private_key: rsa.RSAPrivateKey,
    clerk_user_id: str,
    *,
    email: str = "rag-user@example.com",
    azp: str = "https://contract-hub.example",
    kid: str = "rag-test-kid",
    exp_delta: timedelta = timedelta(hours=1),
    nbf_delta: timedelta = timedelta(seconds=-1),
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": clerk_user_id,
        "email": email,
        "azp": azp,
        "iat": now,
        "exp": now + exp_delta,
        "nbf": now + nbf_delta,
    }
    return jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": kid})


@pytest.fixture
def signing_material():
    return _generate_rsa_keypair()


@pytest.fixture
async def rag_client(signing_material, monkeypatch, db_session):
    _, jwks = signing_material

    monkeypatch.setenv("RAG_FIXED_TENANT_ID", "tenant-fixed-001")
    monkeypatch.setenv("VECTOR_STORE_URL", "http://vector-store.internal:8000")
    monkeypatch.setenv("CLERK_AUTHORIZED_ORIGINS", "https://contract-hub.example")
    get_settings.cache_clear()

    async def override_get_session():
        yield db_session

    monkeypatch.setattr("app.clerk_auth.get_clerk_jwks_for_verification", lambda: jwks)
    app.dependency_overrides[get_clerk_jwks_for_verification] = lambda: jwks
    app.dependency_overrides[get_session] = override_get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()
    get_settings.cache_clear()


def _build_mock_vector_store_client(
    captured_requests: list[dict],
    *,
    response_json: dict | None = None,
    error: Exception | None = None,
    status_code: int = 200,
) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(
            {
                "method": request.method,
                "url": str(request.url),
                "json": json.loads(request.content.decode("utf-8")),
            }
        )
        if error is not None:
            raise error
        return httpx.Response(
            status_code,
            json=response_json or {"query": "", "results": [], "total_found": 0},
        )

    return AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://vector-store.internal:8000",
    )


@pytest.mark.asyncio
async def test_rag_query_accepts_valid_clerk_token_without_platform_user_row(
    rag_client, signing_material
):
    private_key, _ = signing_material
    token = _make_clerk_token(private_key, "clerk-user-001")
    captured_requests: list[dict] = []
    mock_client = _build_mock_vector_store_client(
        captured_requests,
        response_json={
            "query": "Find the contract clause about renewal.",
            "results": [
                {"rank": 1, "text": "renewal clause", "metadata": {"doc_id": "doc-1"}}
            ],
            "total_found": 1,
        },
    )
    constructor_calls: list[dict] = []

    def fake_client_ctor(*args, **kwargs):
        constructor_calls.append(kwargs)
        return mock_client

    with patch("app.rag.httpx.AsyncClient", side_effect=fake_client_ctor):
        response = await rag_client.post(
            "/api/v1/rag/query",
            headers={"Authorization": f"Bearer {token}"},
            json={"query": "Find the contract clause about renewal."},
        )

    assert response.status_code == 200
    assert constructor_calls[0]["base_url"] == "http://vector-store.internal:8000"
    assert len(captured_requests) == 1
    forwarded_request = captured_requests[0]["json"]
    assert forwarded_request == {
        "query": "Find the contract clause about renewal.",
        "n_results": 10,
        "where_filter": {
            "tenant_id": "tenant-fixed-001",
            "clerk_user_id": "clerk-user-001",
        },
    }
    payload = response.json()
    assert payload["scope"] == {
        "tenant_id": "tenant-fixed-001",
        "clerk_user_id": "clerk-user-001",
    }
    assert payload["payload"] == {"query": "Find the contract clause about renewal."}
    assert payload["result"]["total_found"] == 1
    assert payload["result"]["results"][0]["metadata"]["doc_id"] == "doc-1"


@pytest.mark.asyncio
async def test_rag_query_rejects_missing_bearer_token(rag_client):
    response = await rag_client.post(
        "/api/v1/rag/query",
        json={"query": "Anything"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing Authorization header"


@pytest.mark.asyncio
async def test_rag_query_returns_scoped_payload_result_shape(
    rag_client, signing_material
):
    private_key, _ = signing_material
    token = _make_clerk_token(private_key, "clerk-user-002")
    captured_requests: list[dict] = []
    mock_client = _build_mock_vector_store_client(
        captured_requests,
        response_json={
            "query": "Summarize the termination section.",
            "results": [],
            "total_found": 0,
        },
    )
    constructor_calls: list[dict] = []

    def fake_client_ctor(*args, **kwargs):
        constructor_calls.append(kwargs)
        return mock_client

    with patch("app.rag.httpx.AsyncClient", side_effect=fake_client_ctor):
        response = await rag_client.post(
            "/api/v1/rag/query",
            headers={"Authorization": f"Bearer {token}"},
            json={"query": "Summarize the termination section."},
        )

    assert response.status_code == 200
    assert constructor_calls[0]["base_url"] == "http://vector-store.internal:8000"
    assert len(captured_requests) == 1
    forwarded_request = captured_requests[0]["json"]
    assert forwarded_request == {
        "query": "Summarize the termination section.",
        "n_results": 10,
        "where_filter": {
            "tenant_id": "tenant-fixed-001",
            "clerk_user_id": "clerk-user-002",
        },
    }
    payload = response.json()
    assert set(payload) == {"scope", "payload", "result"}
    assert payload["scope"] == {
        "tenant_id": "tenant-fixed-001",
        "clerk_user_id": "clerk-user-002",
    }
    assert payload["payload"] == {"query": "Summarize the termination section."}
    assert payload["result"] == {
        "query": "Summarize the termination section.",
        "results": [],
        "total_found": 0,
    }


@pytest.mark.asyncio
async def test_rag_delete_proxies_scoped_document_delete(rag_client, signing_material):
    private_key, _ = signing_material
    token = _make_clerk_token(private_key, "clerk-user-delete-001")
    captured_requests: list[dict] = []
    mock_client = _build_mock_vector_store_client(
        captured_requests,
        response_json={"deleted": 1},
    )

    def fake_client_ctor(*args, **kwargs):
        return mock_client

    with patch("app.rag.httpx.AsyncClient", side_effect=fake_client_ctor):
        response = await rag_client.delete(
            "/api/v1/rag/documents/doc-delete-001",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert len(captured_requests) == 1
    assert captured_requests[0]["method"] == "POST"
    assert captured_requests[0]["url"] == "http://vector-store.internal:8000/delete"
    assert captured_requests[0]["json"] == {
        "where_filter": {
            "tenant_id": "tenant-fixed-001",
            "clerk_user_id": "clerk-user-delete-001",
            "document_id": "doc-delete-001",
        },
    }
    assert response.json() == {
        "scope": {
            "tenant_id": "tenant-fixed-001",
            "clerk_user_id": "clerk-user-delete-001",
        },
        "payload": {"document_id": "doc-delete-001"},
        "result": {"deleted": 1},
    }


@pytest.mark.asyncio
async def test_rag_stats_proxies_scoped_stats_request(rag_client, signing_material):
    private_key, _ = signing_material
    token = _make_clerk_token(private_key, "clerk-user-stats-001")
    captured_requests: list[dict] = []
    mock_client = _build_mock_vector_store_client(
        captured_requests,
        response_json={
            "total_documents": 3,
            "collection_name": "carbon-agent-documents",
            "embedding_model": "all-MiniLM-L6-v2",
        },
    )

    def fake_client_ctor(*args, **kwargs):
        return mock_client

    with patch("app.rag.httpx.AsyncClient", side_effect=fake_client_ctor):
        response = await rag_client.get(
            "/api/v1/rag/stats",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert len(captured_requests) == 1
    assert captured_requests[0]["method"] == "POST"
    assert captured_requests[0]["url"] == "http://vector-store.internal:8000/stats"
    assert captured_requests[0]["json"] == {
        "where_filter": {
            "tenant_id": "tenant-fixed-001",
            "clerk_user_id": "clerk-user-stats-001",
        },
    }
    assert response.json() == {
        "scope": {
            "tenant_id": "tenant-fixed-001",
            "clerk_user_id": "clerk-user-stats-001",
        },
        "payload": {},
        "result": {
            "total_documents": 3,
            "collection_name": "carbon-agent-documents",
            "embedding_model": "all-MiniLM-L6-v2",
        },
    }


@pytest.mark.asyncio
async def test_rag_query_denies_suspended_carbon_user_row_with_matching_clerk_id(
    rag_client,
    db_session,
    signing_material,
):
    user = User(
        id="carbon-user-001",
        email="matched-by-email@example.com",
        display_name="Suspended RAG User",
        api_key="sk-suspended-rag-key",
        status=UserStatus.SUSPENDED,
        clerk_user_id=None,
    )
    db_session.add(user)
    await db_session.commit()

    private_key, _ = signing_material
    token = _make_clerk_token(
        private_key, "clerk-user-email", email="matched-by-email@example.com"
    )

    response = await rag_client.post(
        "/api/v1/rag/query",
        headers={"Authorization": f"Bearer {token}"},
        json={"query": "Should be denied."},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "User account is not active"


@pytest.mark.asyncio
async def test_rag_query_returns_503_when_vector_store_unavailable(
    rag_client, signing_material
):
    private_key, _ = signing_material
    token = _make_clerk_token(private_key, "clerk-user-003")
    captured_requests: list[dict] = []
    request = httpx.Request("POST", "http://vector-store.internal:8000/search")
    error = httpx.ConnectError("vector store unavailable", request=request)
    mock_client = _build_mock_vector_store_client(captured_requests, error=error)

    def fake_client_ctor(*args, **kwargs):
        return mock_client

    with patch("app.rag.httpx.AsyncClient", side_effect=fake_client_ctor):
        response = await rag_client.post(
            "/api/v1/rag/query",
            headers={"Authorization": f"Bearer {token}"},
            json={"query": "Fail loudly."},
        )

    assert response.status_code == 503
    assert response.json()["detail"] == "Vector store service unavailable"
    assert len(captured_requests) == 1


@pytest.mark.asyncio
async def test_rag_delete_returns_503_when_vector_store_unavailable(
    rag_client, signing_material
):
    private_key, _ = signing_material
    token = _make_clerk_token(private_key, "clerk-user-delete-unavailable")
    captured_requests: list[dict] = []
    request = httpx.Request("POST", "http://vector-store.internal:8000/delete")
    error = httpx.ConnectError("vector store unavailable", request=request)
    mock_client = _build_mock_vector_store_client(captured_requests, error=error)

    def fake_client_ctor(*args, **kwargs):
        return mock_client

    with patch("app.rag.httpx.AsyncClient", side_effect=fake_client_ctor):
        response = await rag_client.delete(
            "/api/v1/rag/documents/doc-delete-503",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 503
    assert response.json()["detail"] == "Vector store service unavailable"
    assert len(captured_requests) == 1


@pytest.mark.asyncio
async def test_rag_stats_returns_502_when_vector_store_errors(
    rag_client, signing_material
):
    private_key, _ = signing_material
    token = _make_clerk_token(private_key, "clerk-user-stats-error")
    captured_requests: list[dict] = []
    mock_client = _build_mock_vector_store_client(
        captured_requests,
        response_json={"detail": "boom"},
        status_code=500,
    )

    def fake_client_ctor(*args, **kwargs):
        return mock_client

    with patch("app.rag.httpx.AsyncClient", side_effect=fake_client_ctor):
        response = await rag_client.get(
            "/api/v1/rag/stats",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 502
    assert response.json()["detail"] == "Vector store stats failed with status 500"
    assert len(captured_requests) == 1


@pytest.mark.asyncio
async def test_rag_query_rejects_azp_mismatch_when_authorized_origins_configured(
    rag_client, signing_material
):
    private_key, _ = signing_material
    token = _make_clerk_token(
        private_key,
        "clerk-user-azp-mismatch",
        azp="https://evil.example",
    )

    response = await rag_client.post(
        "/api/v1/rag/query",
        headers={"Authorization": f"Bearer {token}"},
        json={"query": "Should fail auth."},
    )

    assert response.status_code == 401
    assert "authorized party mismatch" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_rag_query_is_rate_limited_per_verified_clerk_user(
    rag_client, signing_material
):
    private_key, _ = signing_material
    token_one = _make_clerk_token(private_key, "clerk-user-rate-limit-1")
    token_two = _make_clerk_token(private_key, "clerk-user-rate-limit-2")
    captured_requests: list[dict] = []
    limiter.reset()

    def fake_client_ctor(*args, **kwargs):
        return _build_mock_vector_store_client(
            captured_requests,
            response_json={
                "query": "Rate limit check.",
                "results": [],
                "total_found": 0,
            },
        )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        with patch("app.rag.httpx.AsyncClient", side_effect=fake_client_ctor):
            last_response = None
            for _ in range(60):
                last_response = await client.post(
                    "/api/v1/rag/query",
                    headers={"Authorization": f"Bearer {token_one}"},
                    json={"query": "Rate limit check."},
                )
                assert last_response.status_code == 200

            other_user_response = await client.post(
                "/api/v1/rag/query",
                headers={"Authorization": f"Bearer {token_two}"},
                json={"query": "Rate limit check."},
            )

            last_response = await client.post(
                "/api/v1/rag/query",
                headers={"Authorization": f"Bearer {token_one}"},
                json={"query": "Rate limit check."},
            )

    assert last_response is not None
    assert last_response.status_code == 429
    assert other_user_response.status_code == 200
    assert len(captured_requests) == 61


def test_validate_production_config_requires_rag_tenant(monkeypatch):
    settings = type(
        "Settings",
        (),
        {
            "auto_create_tables": False,
            "clerk_secret_key": "set",
            "clerk_publishable_key": "set",
            "clerk_frontend_api_url": "https://clerk.example",
            "clerk_webhook_secret": "set",
            "database_url": "postgresql://example",
            "rag_fixed_tenant_id": "",
        },
    )()

    monkeypatch.setattr("app.main.get_settings", lambda: settings)

    with pytest.raises(ValueError) as exc_info:
        _validate_production_config()

    assert "RAG_FIXED_TENANT_ID" in str(exc_info.value)


def test_validate_production_config_requires_clerk_jwt_issuer(monkeypatch):
    settings = type(
        "Settings",
        (),
        {
            "auto_create_tables": False,
            "clerk_secret_key": "set",
            "clerk_publishable_key": "set",
            "clerk_frontend_api_url": "https://clerk.example",
            "clerk_webhook_secret": "set",
            "database_url": "postgresql://example",
            "rag_fixed_tenant_id": "tenant-fixed-001",
            "clerk_jwt_issuer": "",
        },
    )()

    monkeypatch.setattr("app.main.get_settings", lambda: settings)

    with pytest.raises(ValueError) as exc_info:
        _validate_production_config()

    assert "CLERK_JWT_ISSUER" in str(exc_info.value)
