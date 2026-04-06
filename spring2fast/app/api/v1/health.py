"""Health check endpoint."""

from fastapi import APIRouter

from app.config import settings

router = APIRouter()


@router.get("")
async def health_check():
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "app": settings.app_name,
        "environment": settings.app_env,
    }
