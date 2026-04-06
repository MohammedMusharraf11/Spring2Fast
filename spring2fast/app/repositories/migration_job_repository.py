"""Persistence helpers for migration job progress."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.db_models import JobStatus, MigrationJob


class MigrationJobRepository:
    """Encapsulates job progress persistence operations."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def update_progress(
        self,
        *,
        job_id: str,
        status: str,
        current_step: str | None,
        progress_pct: int | None = None,
        error_message: str | None = None,
        output_path: str | None = None,
        completed_at: datetime | None = None,
    ) -> None:
        async with self.session_factory() as session:
            job = await session.get(MigrationJob, job_id)
            if job is None:
                raise ValueError(f"Migration job not found: {job_id}")

            job.status = JobStatus(status)
            job.current_step = current_step
            if progress_pct is not None:
                job.progress_pct = progress_pct
            job.error_message = error_message
            if output_path is not None:
                job.output_path = output_path
            if completed_at is not None:
                job.completed_at = completed_at

            await session.commit()
