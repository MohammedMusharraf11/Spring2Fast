"""Pydantic schemas used by the API layer."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, HttpUrl


class GitHubMigrateRequest(BaseModel):
    """Payload for a GitHub-based migration request."""

    github_url: HttpUrl
    branch: Optional[str] = None


class MigrationJobResponse(BaseModel):
    """Acknowledgement returned when a migration job is created."""

    job_id: str
    status: str
    message: str


class MigrationStatusResponse(BaseModel):
    """Job status payload returned to clients."""

    job_id: str
    status: str
    current_step: Optional[str] = None
    progress_pct: int = 0
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
