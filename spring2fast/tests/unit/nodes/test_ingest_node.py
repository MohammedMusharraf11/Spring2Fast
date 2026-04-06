"""Tests for the ingestion node."""

from pathlib import Path
from zipfile import ZipFile

from app.agents.nodes.ingest import ingest_node


def test_ingest_node_prepares_workspace_directories(tmp_path: Path) -> None:
    state = {
        "job_id": "job-123",
        "source_type": "folder",
        "source_url": str(tmp_path / "source-project"),
        "workspace_dir": str(tmp_path),
        "status": "pending",
        "current_step": "Job created",
        "progress_pct": 0,
        "logs": [],
        "analysis_artifacts": {},
        "discovered_technologies": [],
        "business_rules": [],
        "generated_files": [],
        "validation_errors": [],
        "retry_count": 0,
        "metadata": {},
    }
    source_project = Path(state["source_url"])
    source_project.mkdir()
    (source_project / "pom.xml").write_text("<project />", encoding="utf-8")

    result = ingest_node(state)

    assert Path(result["input_dir"]).is_dir()
    assert Path(result["artifacts_dir"]).is_dir()
    assert Path(result["output_dir"]).is_dir()
    assert (Path(result["input_dir"]) / "pom.xml").exists()
    assert result["status"] == "ingesting"
    assert result["progress_pct"] == 10
    assert result["metadata"]["ingestion"]["resolved_source_path"].endswith("source-project")


def test_ingest_node_keeps_original_state_unchanged(tmp_path: Path) -> None:
    source_project = tmp_path / "original-source"
    source_project.mkdir()
    state = {
        "job_id": "job-immutable",
        "source_type": "folder",
        "source_url": str(source_project),
        "workspace_dir": str(tmp_path),
        "status": "pending",
        "current_step": "Job created",
        "progress_pct": 0,
        "logs": [],
        "analysis_artifacts": {},
        "discovered_technologies": [],
        "business_rules": [],
        "generated_files": [],
        "validation_errors": [],
        "retry_count": 0,
        "metadata": {},
    }

    _ = ingest_node(state)

    assert "input_dir" not in state
    assert state["status"] == "pending"


def test_ingest_node_extracts_zip_upload(tmp_path: Path) -> None:
    archive_path = tmp_path / "sample.zip"
    with ZipFile(archive_path, "w") as archive:
        archive.writestr("demo/src/main/java/App.java", "class App {}")

    state = {
        "job_id": "job-upload",
        "source_type": "upload",
        "source_url": str(archive_path),
        "workspace_dir": str(tmp_path),
        "status": "pending",
        "current_step": "Job created",
        "progress_pct": 0,
        "logs": [],
        "analysis_artifacts": {},
        "discovered_technologies": [],
        "business_rules": [],
        "generated_files": [],
        "validation_errors": [],
        "retry_count": 0,
        "metadata": {},
    }

    result = ingest_node(state)

    assert (Path(result["input_dir"]) / "demo" / "src" / "main" / "java" / "App.java").exists()
    assert result["metadata"]["ingestion"]["resolved_source_path"] == str(archive_path.resolve())
