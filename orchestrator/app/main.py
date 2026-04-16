"""Orchestrator API - main FastAPI application."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import get_session, init_db, create_tables
from app.admin import admin_router
from app.users import user_router
from app.session_manager import get_session_manager
import structlog

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    init_db()
    await create_tables()
    
    # Start session manager cleanup task
    session_manager = get_session_manager()
    await session_manager.start_cleanup_task()
    
    logger.info("orchestrator_started")
    yield
    
    # Stop session manager cleanup task
    await session_manager.stop_cleanup_task()
    logger.info("orchestrator_stopped")


app = FastAPI(
    title="Carbon Agent Orchestrator",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount admin and user routes
app.include_router(admin_router)
app.include_router(user_router)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "orchestrator"}
