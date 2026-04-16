"""Simple synchronous test client for adapter."""
import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.auth import get_db
from app.main import app
from app.models import Base, User, UserStatus

@pytest.fixture
def client():
    """Create a test client with mocked auth."""
    return TestClient(app)


def test_health_endpoint(client):
    """Test that health endpoint works without authentication."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "service": "carbon-agent-adapter"}


def test_models_endpoint_without_auth(client):
    """Test that models endpoint requires authentication (returns 401)."""
    response = client.get("/v1/models")
    # Should fail with 401 since no auth header provided
    assert response.status_code == 401


def test_list_models_requires_auth(client):
    """Test that models endpoint requires authentication."""
    response = client.get("/v1/models")
    assert response.status_code in [401, 403]


def test_user_info_requires_auth(client):
    """Test that user info endpoint requires authentication."""
    response = client.get("/v1/user")
    assert response.status_code == 401


def test_chat_completions_requires_auth(client):
    """Test that chat completions endpoint requires authentication."""
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "carbon-agent",
            "messages": [{"role": "user", "content": "Hello"}],
        }
    )
    assert response.status_code == 401


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def adapter_client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_old_api_key_rejected_after_rotation(adapter_client, db_session):
    user = User(
        id="adapter-user-rotation-1",
        email="adapter-rotate@test.com",
        display_name="Adapter Rotate User",
        api_key="sk-old-adapter-rotation-key",
        status=UserStatus.ACTIVE,
    )
    db_session.add(user)
    await db_session.commit()

    old_key_ok = await adapter_client.get(
        "/v1/models",
        headers={"Authorization": "Bearer sk-old-adapter-rotation-key"},
    )
    assert old_key_ok.status_code == 200

    user.api_key = "sk-new-adapter-rotation-key"
    await db_session.commit()

    old_key_rejected = await adapter_client.get(
        "/v1/models",
        headers={"Authorization": "Bearer sk-old-adapter-rotation-key"},
    )
    assert old_key_rejected.status_code == 401
    assert old_key_rejected.json()["detail"] == "Invalid API key"

    new_key_ok = await adapter_client.get(
        "/v1/models",
        headers={"Authorization": "Bearer sk-new-adapter-rotation-key"},
    )
    assert new_key_ok.status_code == 200
