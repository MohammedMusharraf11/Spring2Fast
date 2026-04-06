"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.config import settings
from app.core.logging import setup_logging
from app.core.llm import log_model_routing


async def _cleanup_stale_jobs() -> None:
    """Mark in-flight jobs as failed after server restart."""
    import asyncio
    try:
        from app.supabase_client import get_supabase
        db = get_supabase()
        stale_statuses = ["ingesting", "analyzing", "planning", "migrating", "validating"]
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: db.table("migration_jobs")
                .update({"status": "failed", "error_message": "Server restarted mid-migration"})
                .in_("status", stale_statuses)
                .execute()
        )
    except Exception:
        pass  # Non-critical


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    # ── Startup ──
    setup_logging()
    log_model_routing()          # Show which LLM is active for each tier
    await _cleanup_stale_jobs()  # Mark stuck jobs as failed
    settings.workspace_path      # Ensure directories exist
    settings.output_path
    yield
    # ── Shutdown ──


app = FastAPI(
    title=settings.app_name,
    description="Agentic AI system that migrates Java Spring Boot backends to Python FastAPI",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS Middleware ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register Routes ──
app.include_router(api_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "name": settings.app_name,
        "version": "0.1.0",
        "description": "Java Spring Boot → Python FastAPI Migration Agent",
        "docs": "/docs",
    }
