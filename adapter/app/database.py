"""Database configuration for adapter (shared with orchestrator)."""
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.config import get_settings

# Create async engine
settings = get_settings()
engine = create_async_engine(
    settings.database_url,
    echo=False,
)

# Create async session factory
async_session_factory = async_sessionmaker(
    engine,
    expire_on_commit=False,
)
