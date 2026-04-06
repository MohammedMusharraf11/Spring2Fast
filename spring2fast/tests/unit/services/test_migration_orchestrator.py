"""Tests for migration orchestrator persistence behavior."""

from __future__ import annotations

from pathlib import Path
import uuid

import pytest

from app.database import async_session, engine
from app.models.db_models import Base, JobStatus, MigrationJob
from app.services.migration_orchestrator import MigrationOrchestrator


@pytest.mark.asyncio
async def test_orchestrator_updates_job_status_to_completed(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("app.config.settings.workspace_dir", str(tmp_path / "workspace"))
    job_id = f"job-db-complete-{uuid.uuid4()}"

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    job = MigrationJob(
        id=job_id,
        source_type="folder",
        source_url=str(tmp_path / "source"),
        status=JobStatus.PENDING,
    )
    source_dir = Path(job.source_url)
    source_dir.mkdir()
    (source_dir / "pom.xml").write_text("<project />", encoding="utf-8")

    async with async_session() as session:
        session.add(job)
        await session.commit()

    orchestrator = MigrationOrchestrator()
    result = await orchestrator.run_migration(
        job_id=job.id,
        source_type="folder",
        source_url=job.source_url,
    )

    async with async_session() as session:
        persisted = await session.get(MigrationJob, job.id)

    assert result["status"] == "completed"
    assert persisted is not None
    assert persisted.status == JobStatus.COMPLETED
    assert persisted.progress_pct == 100
    assert persisted.current_step == "Initial workflow scaffold completed"
    assert persisted.completed_at is not None


@pytest.mark.asyncio
async def test_orchestrator_marks_job_failed_on_error(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("app.config.settings.workspace_dir", str(tmp_path / "workspace"))
    job_id = f"job-db-failed-{uuid.uuid4()}"

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    job = MigrationJob(
        id=job_id,
        source_type="folder",
        source_url=str(tmp_path / "missing-source"),
        status=JobStatus.PENDING,
    )

    async with async_session() as session:
        session.add(job)
        await session.commit()

    orchestrator = MigrationOrchestrator()

    with pytest.raises(FileNotFoundError):
        await orchestrator.run_migration(
            job_id=job.id,
            source_type="folder",
            source_url=job.source_url,
        )

    async with async_session() as session:
        persisted = await session.get(MigrationJob, job.id)

    assert persisted is not None
    assert persisted.status == JobStatus.FAILED
    assert persisted.current_step == "Migration workflow failed"
    assert persisted.error_message is not None
