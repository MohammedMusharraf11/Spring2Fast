"""Tests for the technology discovery node."""

import asyncio
from pathlib import Path

from app.agents.nodes.tech_discover import tech_discover_node


def test_tech_discover_node_updates_state_and_writes_artifact(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    artifacts_dir = tmp_path / "artifacts"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    artifacts_dir.mkdir()
    output_dir.mkdir()

    (input_dir / "build.gradle").write_text(
        """
        dependencies {
          implementation 'org.springframework.boot:spring-boot-starter-web'
          implementation 'org.springframework.boot:spring-boot-starter-data-redis'
        }
        """,
        encoding="utf-8",
    )
    (input_dir / "DemoApplication.java").write_text(
        """
        @SpringBootApplication
        public class DemoApplication {}
        """,
        encoding="utf-8",
    )

    state = {
        "job_id": "job-tech",
        "source_type": "folder",
        "source_url": str(input_dir),
        "workspace_dir": str(tmp_path),
        "input_dir": str(input_dir),
        "artifacts_dir": str(artifacts_dir),
        "output_dir": str(output_dir),
        "status": "ingesting",
        "current_step": "Acquired source code into migration workspace",
        "progress_pct": 10,
        "logs": [],
        "analysis_artifacts": {},
        "discovered_technologies": [],
        "business_rules": [],
        "generated_files": [],
        "validation_errors": [],
        "retry_count": 0,
        "metadata": {},
    }

    result = asyncio.run(tech_discover_node(state))

    assert result["status"] == "analyzing"
    assert result["progress_pct"] == 25
    assert "spring-web" in result["discovered_technologies"]
    assert "redis" in result["discovered_technologies"]
    artifact_path = Path(result["analysis_artifacts"]["technology_inventory"])
    assert artifact_path.exists()
    assert result["metadata"]["technology_inventory"]["java_file_count"] == 1
