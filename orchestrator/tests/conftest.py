"""Shared test fixtures."""
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.database import Base
from app.models import User

@pytest_asyncio.fixture
async def engine():
    engine = create_async_engine("sqlite+aiosqlite:///test.db", echo=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest_asyncio.fixture
async def db_session(engine) -> AsyncSession:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()

@pytest.fixture
def sample_user_data():
    return {
        "id": "usr-001",
        "email": "test@example.com",
        "display_name": "Test User",
        "api_key": "sk-test-key-001",
        "status": "active",
    }
