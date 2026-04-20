"""Quick diagnostic test."""

import pytest
from sqlalchemy.ext.asyncio import create_async_engine


@pytest.mark.asyncio
async def test_basic_async():
    print("basic async works")
    assert True


@pytest.mark.asyncio
async def test_sqlite_engine():
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        result = await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        assert result.scalar() == 1
    await engine.dispose()
    print("sqlite engine works")
