"""Tests for the scaffolded migration graph."""

import asyncio
from pathlib import Path
from unittest.mock import patch

from app.agents.graph import build_migration_graph


def test_graph_runs_end_to_end_with_scaffold(tmp_path: Path) -> None:
    graph = build_migration_graph()
    state = {
        "job_id": "job-graph",
        "source_type": "github",
        "source_url": "https://github.com/example/project",
        "branch": "main",
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

    with patch("app.services.ingestion_service.Repo.clone_from") as clone_from:
        result = asyncio.run(graph.ainvoke(state))

    assert result["status"] == "completed"
    assert result["progress_pct"] == 100
    assert Path(result["input_dir"]).is_dir()
    assert "technology_inventory" in result["analysis_artifacts"]
    assert "business_rules" in result["analysis_artifacts"]
    assert "component_inventory" in result["analysis_artifacts"]
    assert "integration_mapping" in result["analysis_artifacts"]
    assert "migration_plan" in result["analysis_artifacts"]
    assert result["generated_files"]
    assert "Initial workflow scaffold completed" in result["logs"]
    clone_from.assert_called_once()
