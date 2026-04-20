"""Orchestrator API - main FastAPI application."""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.database import get_session, init_db, create_tables
from app.admin import admin_router
from app.admin_ui import admin_ui_router
from app.users import user_router
from app.clerk import clerk_webhook_router
from app.auth_routes import auth_router
from app.rag import ClerkRAGIdentityMiddleware, rag_router
from app.session_manager import get_session_manager
from app.scheduler import get_scheduler
from app.api_key_injection import ApiKeyInjectionMiddleware
from app.config import get_settings
from app.rate_limit import limiter, rate_limit_exceeded_handler
from app.metrics import RequestIDMiddleware, metrics_endpoint
import structlog

logger = structlog.get_logger()


class DBSessionMiddleware(BaseHTTPMiddleware):
    """Middleware that provides a database session via request.state."""

    async def dispatch(self, request, call_next):
        from app.database import get_session
        async for session in get_session():
            request.state.db = session
            try:
                response = await call_next(request)
            finally:
                await session.close()
            return response
        # Fallback if no session yielded (shouldn't happen in practice)
        response = await call_next(request)
        return response


def _validate_production_config() -> None:
    """Fail-fast check for required env vars in production mode.

    Called from lifespan when auto_create_tables=False (i.e. production).
    Raises ValueError with a descriptive message for any missing critical var.
    """
    s = get_settings()
    missing = []

    required = {
        "clerk_secret_key":        "CLERK_SECRET_KEY",
        "clerk_publishable_key":   "CLERK_PUBLISHABLE_KEY",
        "clerk_frontend_api_url":  "CLERK_FRONTEND_API_URL",
        "clerk_webhook_secret":    "CLERK_WEBHOOK_SECRET",
        "clerk_jwt_issuer":        "CLERK_JWT_ISSUER",
        "database_url":            "DATABASE_URL",
        "rag_fixed_tenant_id":      "RAG_FIXED_TENANT_ID",
    }
    for attr, env_name in required.items():
        val = getattr(s, attr, "")
        if not val or val in ("", "changeme", "your-token-here"):
            missing.append(env_name)

    if missing:
        raise ValueError(
            f"Production startup aborted. Missing required env vars: {', '.join(missing)}. "
            "Set them in your Railway / .env.production file."
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    init_db()

    # In production, verify all required env vars before doing anything else.
    if not get_settings().auto_create_tables:
        _validate_production_config()

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


# ── CORS configuration ────────────────────────────────────────────────────────
_settings = get_settings()
_cors_origins_str = _settings.cors_allowed_origins.strip()

if _cors_origins_str:
    _cors_origins = [o.strip() for o in _cors_origins_str.split(",") if o.strip()]
elif _settings.auto_create_tables:
    # Development / test mode: allow localhost by default
    _cors_origins = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://localhost:8001",
    ]
    logger.warning(
        "cors_using_localhost_fallback",
        hint="Set CORS_ALLOWED_ORIGINS explicitly for any non-local deployment.",
    )
else:
    # Production mode (auto_create_tables=False) with no origins configured:
    # fail fast rather than silently opening CORS to nothing or defaulting to localhost.
    raise ValueError(
        "CORS_ALLOWED_ORIGINS must be set in production (auto_create_tables=False). "
        "Example: CORS_ALLOWED_ORIGINS=https://your-dashboard.example.com"
    )
# ─────────────────────────────────────────────────────────────────────────────


app = FastAPI(
    title="Carbon Agent Orchestrator",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request ID and metrics middleware (before other middlewares for full coverage)
app.add_middleware(RequestIDMiddleware)

# DB session middleware must come before API key injection
app.add_middleware(DBSessionMiddleware)

# API key injection for adapter-bound requests
app.add_middleware(ApiKeyInjectionMiddleware)

# Clerk identity propagation for RAG rate limiting must happen before SlowAPI.
app.add_middleware(ClerkRAGIdentityMiddleware)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Routers
app.include_router(admin_router)
app.include_router(admin_ui_router)
app.include_router(user_router)
app.include_router(auth_router)
app.include_router(clerk_webhook_router)
app.include_router(rag_router)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "orchestrator"}


# Metrics endpoint for Prometheus scraping
app.add_api_route("/metrics", metrics_endpoint, methods=["GET"])
