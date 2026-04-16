"""Orchestrator API - main FastAPI application."""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session, init_db, create_tables
from app.admin import admin_router
from app.router import AgentRouter
from app.session_manager import SessionManager
from app.railway import RailwayClient
from app.config import get_settings
import structlog

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    init_db()
    await create_tables()
    logger.info("orchestrator_started")
    yield
    logger.info("orchestrator_stopped")


app = FastAPI(
    title="Carbon Agent Orchestrator",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount admin routes
app.include_router(admin_router)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "orchestrator"}


@app.post("/v1/chat/completions")
async def proxy_chat(
    request: Request,
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_session),
):
    """Proxy endpoint that Open WebUI calls.

    Extracts the API key from Authorization header,
    looks up the user, ensures their agent is running,
    then proxies the request.
    """
    settings = get_settings()

    # Extract API key
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    api_key = authorization[7:]

    # Set up router
    railway = RailwayClient(
        api_token=settings.railway_api_token,
        project_id=settings.railway_project_id,
        environment_id=settings.railway_environment_id,
    )
    session_manager = SessionManager(railway, settings)
    router = AgentRouter(session_manager)

    # Resolve user
    user = await router.resolve_user(api_key, db)

    # Get or create session
    session = await router.get_or_create_session(user, db)

    # Proxy request
    return await router.proxy_request(session, request)
