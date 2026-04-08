"""Tests for the assemble node."""

from pathlib import Path

from app.agents.nodes.assemble import assemble_node


def test_assemble_node_generates_infrastructure_and_packaging(tmp_path: Path) -> None:
    output_dir = tmp_path / "output"
    artifacts_dir = tmp_path / "artifacts"
    output_dir.mkdir()
    artifacts_dir.mkdir()
    (output_dir / "app" / "main.py").parent.mkdir(parents=True)
    (output_dir / "app" / "main.py").write_text("from yourapp.api import router\n", encoding="utf-8")

    state = {
        "job_id": "job-assemble",
        "source_type": "folder",
        "source_url": str(tmp_path),
        "workspace_dir": str(tmp_path),
        "input_dir": str(tmp_path / "input"),
        "artifacts_dir": str(artifacts_dir),
        "output_dir": str(output_dir),
        "status": "validating",
        "current_step": "Validation passed",
        "progress_pct": 90,
        "logs": [],
        "analysis_artifacts": {},
        "discovered_technologies": ["spring-security", "redis"],
        "business_rules": [],
        "generated_files": ["app/main.py"],
        "validation_errors": [],
        "retry_count": 0,
        "metadata": {
            "component_inventory": {
                "controllers": [{"class_name": "OwnerController"}],
                "services": [{"class_name": "OwnerService"}],
                "entities": [{"class_name": "Owner"}],
            }
        },
    }

    result = assemble_node(state)

    assert result["status"] == "completed"
    assert (output_dir / "app" / "db" / "session.py").exists()
    assert (output_dir / "app" / "core" / "security.py").exists()
    assert (output_dir / "Dockerfile").exists()
    assert (output_dir / "docker-compose.yml").exists()
    assert (output_dir / "alembic" / "env.py").exists()
    assert (output_dir / "tests" / "test_owner_api.py").exists()
    assert (artifacts_dir / "fastapi_project_job-asse.zip").exists()
    assert "app" in (output_dir / "app" / "main.py").read_text(encoding="utf-8")
