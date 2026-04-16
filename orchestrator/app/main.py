"""Orchestrator API - main FastAPI application."""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.database import get_session, init_db, create_tables
from app.admin import admin_router
from app.admin_ui import admin_ui_router
from app.users import user_router
from app.clerk import clerk_webhook_router
from app.auth_routes import auth_router
from app.session_manager import get_session_manager
from app.scheduler import get_scheduler
from app.api_key_injection import ApiKeyInjectionMiddleware
from app.config import get_settings
import structlog

logger = structlog.get_logger()

# Rate limiter - uses remote IP as default key
limiter = Limiter(key_func=get_remote_address)


class DBSessionMiddleware(BaseHTTPMiddleware):
    """Middleware that provides a database session via request.state."""

    async def dispatch(self, request, call_next):
        from app.database import get_session
        async for session in get_session():
            request.state.db = session
            response = await call_next(request)
            await session.close()
            return response
        # Fallback if no session yielded
        response = await call_next(request)
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    init_db()

    # In dev/test, auto-create tables. In production, rely on Alembic migrations.
    if get_settings().auto_create_tables:
        await create_tables()

    # Start session manager cleanup task
    session_manager = get_session_manager()
    await session_manager.start_cleanup_task()

    # Start scheduler for platform background tasks
    scheduler = get_scheduler()
    await scheduler.start()

    logger.info("orchestrator_started")
    yield

    # Stop scheduler
    await scheduler.stop()

    # Stop session manager cleanup task
    await session_manager.stop_cleanup_task()
    logger.info("orchestrator_stopped")


app = FastAPI(
    title="Carbon Agent Orchestrator",
    version="2.0.0",
    lifespan=lifespan,
)

# Configure CORS from environment variable
_settings = get_settings()
_cors_origins_str = _settings.cors_allowed_origins.strip()
if _cors_origins_str:
    _cors_origins = [o.strip() for o in _cors_origins_str.split(",") if o.strip()]
else:
    # Default to localhost for development
    _cors_origins = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://localhost:8001",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add DB session middleware (must be before API key injection)
app.add_middleware(DBSessionMiddleware)

# Add API key injection middleware for adapter-bound requests
app.add_middleware(ApiKeyInjectionMiddleware)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Mount admin, user, auth, Clerk webhook, and admin UI routes
app.include_router(admin_router)
app.include_router(admin_ui_router)
app.include_router(user_router)
app.include_router(auth_router)
app.include_router(clerk_webhook_router)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "orchestrator"}
