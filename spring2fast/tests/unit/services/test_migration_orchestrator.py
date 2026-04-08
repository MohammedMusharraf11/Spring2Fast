"""Tests for migration orchestrator behavior."""

from __future__ import annotations

import asyncio
from pathlib import Path
import uuid

from app.services.migration_orchestrator import MigrationOrchestrator


class _FakeJobRepository:
    def __init__(self) -> None:
        self.updates: list[dict] = []

    async def update_progress(self, **payload) -> None:
        self.updates.append(payload)


def test_orchestrator_updates_job_status_to_completed(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("app.config.settings.workspace_dir", str(tmp_path / "workspace"))
    monkeypatch.setattr("app.services.migration_orchestrator.MigrationJobRepository", _FakeJobRepository)

    job_id = f"job-db-complete-{uuid.uuid4()}"
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "pom.xml").write_text("<project />", encoding="utf-8")

    orchestrator = MigrationOrchestrator()
    result = asyncio.run(
        orchestrator.run_migration(
            job_id=job_id,
            source_type="folder",
            source_url=str(source_dir),
        )
    )

    state_file = Path(tmp_path / "workspace" / job_id / "artifacts" / "_state.json")

    assert result["status"] == "completed"
    assert result["progress_pct"] == 100
    assert state_file.exists()
    assert orchestrator.job_repository.updates[-1]["status"] == "completed"
    assert orchestrator.job_repository.updates[-1]["output_path"]


def test_orchestrator_marks_job_failed_on_error(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("app.config.settings.workspace_dir", str(tmp_path / "workspace"))
    monkeypatch.setattr("app.services.migration_orchestrator.MigrationJobRepository", _FakeJobRepository)

    job_id = f"job-db-failed-{uuid.uuid4()}"
    orchestrator = MigrationOrchestrator()

    try:
        asyncio.run(
            orchestrator.run_migration(
                job_id=job_id,
                source_type="folder",
                source_url=str(tmp_path / "missing-source"),
            )
        )
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("Expected FileNotFoundError")

    assert orchestrator.job_repository.updates[-1]["status"] == "failed"
    assert "error_message" in orchestrator.job_repository.updates[-1]
