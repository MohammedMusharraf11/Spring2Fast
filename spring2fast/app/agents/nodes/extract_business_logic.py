"""Business logic extraction node."""

from __future__ import annotations

from copy import deepcopy

from app.agents.state import MigrationState
from app.services.business_logic_service import BusinessLogicService


def extract_business_logic_node(state: MigrationState) -> MigrationState:
    """Extract business rules and persist them as a markdown artifact."""
    next_state = deepcopy(state)
    result = BusinessLogicService().extract(
        input_dir=next_state["input_dir"],
        artifacts_dir=next_state["artifacts_dir"],
    )

    next_state["status"] = "analyzing"
    next_state["current_step"] = "Extracted Java business rules"
    next_state["progress_pct"] = 40
    next_state["business_rules"] = result.rules
    next_state["analysis_artifacts"] = {
        **next_state["analysis_artifacts"],
        "business_rules": str(result.artifact_path),
    }
    next_state["logs"] = [
        *next_state["logs"],
        f"Extracted {len(result.rules)} business rule hints",
    ]
    next_state["metadata"] = {
        **next_state["metadata"],
        "business_logic": {
            "classes_analyzed": result.classes_analyzed,
            "llm_summary": result.llm_summary,
        },
    }
    return next_state
