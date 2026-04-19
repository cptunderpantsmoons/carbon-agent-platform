"""Database configuration for adapter (shared with orchestrator)."""
import sys
import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.config import get_settings

# Create async engine
settings = get_settings()
print(f"DEBUG: database_url = {settings.database_url}", file=sys.stderr)
sys.stderr.flush()
print(f"DEBUG: DATABASE_URL env = {os.getenv('DATABASE_URL')}", file=sys.stderr)
sys.stderr.flush()
engine = create_async_engine(
    settings.database_url,
    echo=False,
)

# Create async session factory
async_session_factory = async_sessionmaker(
    engine,
    expire_on_commit=False,
)
