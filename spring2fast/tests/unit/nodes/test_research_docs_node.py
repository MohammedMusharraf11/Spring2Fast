"""Tests for the docs-research node."""

import asyncio
from pathlib import Path

from app.agents.nodes.research_docs import research_docs_node


def test_research_docs_node_updates_state_and_artifact(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "artifacts"
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    artifacts_dir.mkdir()
    input_dir.mkdir()
    output_dir.mkdir()

    state = {
        "job_id": "job-docs",
        "source_type": "folder",
        "source_url": str(input_dir),
        "workspace_dir": str(tmp_path),
        "input_dir": str(input_dir),
        "artifacts_dir": str(artifacts_dir),
        "output_dir": str(output_dir),
        "status": "analyzing",
        "current_step": "Extracted Java business rules",
        "progress_pct": 40,
        "logs": [],
        "analysis_artifacts": {},
        "discovered_technologies": ["spring-boot", "spring-security", "postgresql"],
        "business_rules": ["StudentController.saveStudentInformation: throws InvalidFieldException"],
        "generated_files": [],
        "validation_errors": [],
        "retry_count": 0,
        "metadata": {},
    }

    result = asyncio.run(research_docs_node(state))

    assert result["status"] == "planning"
    assert result["progress_pct"] == 50
    assert "integration_mapping" in result["analysis_artifacts"]
    artifact_path = Path(result["analysis_artifacts"]["integration_mapping"])
    assert artifact_path.exists()
    assert result["metadata"]["docs_research"]["reference_count"] == 3
