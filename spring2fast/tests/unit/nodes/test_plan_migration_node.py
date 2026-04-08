"""Tests for the migration planning node."""

import asyncio
from pathlib import Path

from app.agents.nodes.plan_migration import plan_migration_node


def test_plan_migration_node_updates_state_and_artifact(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "artifacts"
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    artifacts_dir.mkdir()
    input_dir.mkdir()
    output_dir.mkdir()

    state = {
        "job_id": "job-plan",
        "source_type": "folder",
        "source_url": str(input_dir),
        "workspace_dir": str(tmp_path),
        "input_dir": str(input_dir),
        "artifacts_dir": str(artifacts_dir),
        "output_dir": str(output_dir),
        "status": "planning",
        "current_step": "Mapped official Python-equivalent documentation",
        "progress_pct": 50,
        "logs": [],
        "analysis_artifacts": {},
        "discovered_technologies": ["spring-boot", "spring-security", "spring-data-jpa"],
        "business_rules": ["OrderService.submitOrder: persists data"],
        "generated_files": [],
        "validation_errors": [],
        "retry_count": 0,
        "metadata": {
            "docs_research": {
                "references": [
                    {"java_technology": "spring-boot", "python_equivalent": "fastapi", "official_docs": "https://fastapi.tiangolo.com/", "notes": "Web framework"}
                ]
            }
        },
    }

    result = asyncio.run(plan_migration_node(state))

    assert result["status"] == "planning"
    assert result["progress_pct"] == 50 or result["progress_pct"] == 40
    assert "migration_plan" in result["analysis_artifacts"]
    artifact_path = Path(result["analysis_artifacts"]["migration_plan"])
    assert artifact_path.exists()
    assert "target_files" in result["metadata"]["migration_plan"]
    assert result["metadata"]["migration_plan"]["target_files"]
