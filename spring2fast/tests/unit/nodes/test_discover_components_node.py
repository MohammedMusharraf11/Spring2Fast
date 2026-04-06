"""Tests for the component discovery node."""

from pathlib import Path

from app.agents.nodes.discover_components import discover_components_node


def test_discover_components_node_updates_state_and_artifact(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    artifacts_dir = tmp_path / "artifacts"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    artifacts_dir.mkdir()
    output_dir.mkdir()

    (input_dir / "OrderController.java").write_text(
        """
        @RestController
        public class OrderController {
            @GetMapping("/orders")
            public String getOrders() { return "ok"; }
        }
        """,
        encoding="utf-8",
    )

    state = {
        "job_id": "job-components",
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
        "discovered_technologies": ["spring-boot", "spring-web"],
        "business_rules": [],
        "generated_files": [],
        "validation_errors": [],
        "retry_count": 0,
        "metadata": {},
    }

    result = discover_components_node(state)

    assert result["progress_pct"] == 45
    assert "component_inventory" in result["analysis_artifacts"]
    assert result["metadata"]["component_inventory"]["controllers"]
    assert Path(result["analysis_artifacts"]["component_inventory"]).exists()
