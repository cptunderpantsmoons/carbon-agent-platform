"""Shared test fixtures."""
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.database import Base
from app.models import User


@pytest.fixture
async def engine():
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_session(engine):
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
def sample_user_data():
    return {
        "id": "user-001",
        "email": "test@example.com",
        "display_name": "Test User",
        "api_key": "sk-test-api-key-12345",
        "status": "active",
    }


@pytest.fixture
def sample_session_data():
    return {
        "id": "session-001",
        "user_id": "user-001",
        "status": "active",
        "internal_url": "http://agent-001.internal:8000",
        "public_url": "https://agent-001.up.railway.app",
    }
