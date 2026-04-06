"""Technology discovery node."""

from __future__ import annotations

from copy import deepcopy

from app.agents.state import MigrationState
from app.services.technology_inventory_service import TechnologyInventoryService


def tech_discover_node(state: MigrationState) -> MigrationState:
    """Scan the ingested project and persist a technology inventory artifact."""
    next_state = deepcopy(state)
    service = TechnologyInventoryService()
    result = service.scan_project(
        input_dir=next_state["input_dir"],
        artifacts_dir=next_state["artifacts_dir"],
    )

    next_state["status"] = "analyzing"
    next_state["current_step"] = "Discovered Java backend technologies"
    next_state["progress_pct"] = 25
    next_state["discovered_technologies"] = result.technologies
    next_state["analysis_artifacts"] = {
        **next_state["analysis_artifacts"],
        "technology_inventory": str(result.artifact_path),
    }
    next_state["logs"] = [
        *next_state["logs"],
        f"Discovered {len(result.technologies)} technology signals",
    ]
    next_state["metadata"] = {
        **next_state["metadata"],
        "technology_inventory": {
            "build_systems": result.build_systems,
            "java_file_count": result.java_file_count,
            "build_files": result.build_files,
            "notes": result.notes,
        },
    }
    return next_state
