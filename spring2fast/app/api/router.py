"""Main API router that aggregates all v1 endpoints."""

from fastapi import APIRouter

from app.api.v1.health import router as health_router
from app.api.v1.migrate import router as migrate_router

api_router = APIRouter()

api_router.include_router(health_router, prefix="/health", tags=["Health"])
api_router.include_router(migrate_router, prefix="/migrate", tags=["Migration"])
