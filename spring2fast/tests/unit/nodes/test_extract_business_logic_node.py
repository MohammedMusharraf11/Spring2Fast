"""Tests for the business logic extraction node."""

import asyncio
from pathlib import Path

from app.agents.nodes.extract_business_logic import extract_business_logic_node


def test_extract_business_logic_node_updates_state_and_artifact(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    artifacts_dir = tmp_path / "artifacts"
    output_dir = tmp_path / "output"
    service_dir = input_dir / "service"
    service_dir.mkdir(parents=True)
    artifacts_dir.mkdir()
    output_dir.mkdir()

    (service_dir / "OrderService.java").write_text(
        """
        public class OrderService {
            public void submitOrder(Order order) {
                if (order == null) {
                    throw new IllegalArgumentException("order required");
                }
                orderRepository.save(order);
            }
        }
        """,
        encoding="utf-8",
    )

    state = {
        "job_id": "job-biz",
        "source_type": "folder",
        "source_url": str(input_dir),
        "workspace_dir": str(tmp_path),
        "input_dir": str(input_dir),
        "artifacts_dir": str(artifacts_dir),
        "output_dir": str(output_dir),
        "status": "analyzing",
        "current_step": "Discovered Java backend technologies",
        "progress_pct": 25,
        "logs": [],
        "analysis_artifacts": {},
        "discovered_technologies": [],
        "business_rules": [],
        "generated_files": [],
        "validation_errors": [],
        "retry_count": 0,
        "metadata": {},
    }

    result = asyncio.run(extract_business_logic_node(state))

    assert result["current_step"] == "Extracted Java business rules"
    assert result["progress_pct"] == 40
    assert result["business_rules"]
    artifact_path = Path(result["analysis_artifacts"]["business_rules"])
    assert artifact_path.exists()
    assert result["metadata"]["business_logic"]["classes_analyzed"] == ["OrderService"]
