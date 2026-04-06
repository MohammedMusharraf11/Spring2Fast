"""Analysis node."""

from __future__ import annotations

from copy import deepcopy

from app.agents.state import MigrationState
from app.services.analysis_service import AnalysisService


def analyze_node(state: MigrationState) -> MigrationState:
    """Analyze dependencies and architecture of the Java source project."""
    next_state = deepcopy(state)
    result = AnalysisService().analyze(
        artifacts_dir=next_state["artifacts_dir"],
        discovered_technologies=next_state["discovered_technologies"],
        business_rules=next_state["business_rules"],
    )

    next_state["status"] = "analyzing"
    next_state["current_step"] = "Analyzed architecture and dependencies"
    next_state["progress_pct"] = 50
    next_state["analysis_artifacts"] = {
        **next_state["analysis_artifacts"],
        "architecture_analysis": str(result.artifact_path),
    }
    next_state["logs"] = [
        *next_state["logs"],
        f"Analyzed {len(result.dependency_graph)} dependency layers",
    ]
    next_state["metadata"] = {
        **next_state["metadata"],
        "architecture_analysis": {
            "dependency_graph": result.dependency_graph,
            "analysis_summary": result.analysis_summary,
        },
    }
    return next_state
