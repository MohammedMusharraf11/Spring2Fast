"""Health check endpoint."""

from fastapi import APIRouter

from app.config import settings

router = APIRouter()


@router.get("")
async def health_check():
    """Basic health check endpoint."""
    # Resolve GitHub token from either env var name
    gh_token = settings.github_pat or settings.github_token or None

    return {
        "status": "healthy",
        "app": settings.app_name,
        "environment": settings.app_env,
        "providers": {
            "bedrock": bool(settings.bedrock_aws_access_key_id and settings.bedrock_aws_secret_access_key),
            "groq":    bool(settings.groq_api_key),
            "gemini":  bool(settings.google_api_key),
        },
        "github": {
            "configured": bool(gh_token),
            # Return MASKED token so frontend can pre-fill (never log full token)
            "token_hint":  f"{gh_token[:8]}..." if gh_token else None,
        },
    }
