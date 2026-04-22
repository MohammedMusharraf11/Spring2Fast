"""Tests for the scaffolded migration graph."""

import asyncio
from pathlib import Path
from unittest.mock import patch

from app.agents.graph import build_migration_graph
from app.agents.migration_subgraph.quality_gate import quality_gate_node


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
    assert any("Packaged result into" in item for item in result["logs"])
    clone_from.assert_called_once()


def test_quality_gate_requeues_failed_components_even_after_inner_retries() -> None:
    state = {
        "completed_conversions": [],
        "failed_conversions": [
            {
                "component_name": "AccountService",
                "component_type": "service",
                "attempts": 4,
                "original_component": {"class_name": "AccountService"},
            }
        ],
        "retry_count": 0,
        "logs": [],
    }

    result = quality_gate_node(state)

    assert result["retry_count"] == 1
    assert result["status"] == "migrating"
    assert len(result["conversion_queue"]) == 1
    assert result["conversion_queue"][0]["component"]["class_name"] == "AccountService"


def test_quality_gate_rebuilds_model_init_exports(tmp_path: Path) -> None:
    output_dir = tmp_path / "output"
    models_dir = output_dir / "app" / "models"
    models_dir.mkdir(parents=True)
    (models_dir / "user.py").write_text("class User:\n    pass\n", encoding="utf-8")

    result = quality_gate_node(
        {
            "completed_conversions": [{"passed": True, "output_path": "app/models/user.py"}],
            "failed_conversions": [],
            "retry_count": 0,
            "generated_files": [],
            "logs": [],
            "output_dir": str(output_dir),
        }
    )

    init_text = (models_dir / "__init__.py").read_text(encoding="utf-8")
    assert 'from app.models.user import User' in init_text
    assert '"User"' in init_text
    assert result["status"] == "validating"
