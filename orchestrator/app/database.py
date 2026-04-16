"""Database connection and session management."""
from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.config import get_settings

class Base(DeclarativeBase):
    pass

_engine = None
_session_factory = None

def _get_database_url() -> str:
    url = get_settings().database_url
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://")
    return url

def init_db():
    global _engine, _session_factory
    _engine = create_async_engine(_get_database_url(), echo=False)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    if _session_factory is None:
        init_db()
    async with _session_factory() as session:
        yield session

async def create_tables():
    if _engine is None:
        init_db()
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
