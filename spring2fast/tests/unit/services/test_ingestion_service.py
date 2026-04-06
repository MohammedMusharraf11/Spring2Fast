"""Tests for the ingestion service."""

from pathlib import Path
from unittest.mock import patch

from app.services.ingestion_service import IngestionService


def test_ingestion_service_clones_github_source(tmp_path: Path) -> None:
    service = IngestionService()

    with patch("app.services.ingestion_service.Repo.clone_from") as clone_from:
        result = service.ingest_source(
            job_id="job-github",
            workspace_dir=str(tmp_path),
            source_type="github",
            source_url="https://github.com/example/demo",
            branch="main",
        )

    clone_from.assert_called_once()
    _, kwargs = clone_from.call_args
    assert kwargs["branch"] == "main"
    assert kwargs["single_branch"] is True
    assert result.input_dir.exists()
    assert result.metadata["resolved_source_path"] == str(result.input_dir)


def test_ingestion_service_copies_folder_source(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "application.yml").write_text("server: {}", encoding="utf-8")

    service = IngestionService()
    result = service.ingest_source(
        job_id="job-folder",
        workspace_dir=str(tmp_path / "workspace"),
        source_type="folder",
        source_url=str(source_dir),
    )

    assert (result.input_dir / "application.yml").exists()
    assert result.metadata["resolved_source_path"] == str(source_dir.resolve())
