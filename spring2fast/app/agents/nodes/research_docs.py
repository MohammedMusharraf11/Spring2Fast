"""Official-docs research node."""

from __future__ import annotations

from copy import deepcopy

from app.agents.state import MigrationState
from app.services.docs_research_service import DocsResearchService


async def research_docs_node(state: MigrationState) -> MigrationState:
    """Map discovered technologies to official Python-equivalent docs."""
    next_state = deepcopy(state)
    result = await DocsResearchService().build_references(
        technologies=next_state["discovered_technologies"],
        artifacts_dir=next_state["artifacts_dir"],
    )

    next_state["status"] = "planning"
    next_state["current_step"] = "Mapped official Python-equivalent documentation"
    next_state["progress_pct"] = 50
    next_state["analysis_artifacts"] = {
        **next_state["analysis_artifacts"],
        "integration_mapping": str(result.artifact_path),
    }
    next_state["logs"] = [
        *next_state["logs"],
        f"Mapped {len(result.references)} official docs references",
    ]
    next_state["metadata"] = {
        **next_state["metadata"],
        "docs_research": {
            "reference_count": len(result.references),
            "references": result.references,
        },
    }
    return next_state
