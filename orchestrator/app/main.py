"""Orchestrator API - main FastAPI application."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import get_session, init_db, create_tables
from app.admin import admin_router
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

# Mount admin routes
app.include_router(admin_router)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "orchestrator"}
