"""Ingestion node for source workspace preparation."""

from __future__ import annotations

from copy import deepcopy

from app.agents.state import MigrationState
from app.services.ingestion_service import IngestionService


def ingest_node(state: MigrationState) -> MigrationState:
    """Acquire the input source and prepare workspace directories."""
    next_state = deepcopy(state)
    service = IngestionService()
    ingestion_result = service.ingest_source(
        job_id=next_state["job_id"],
        workspace_dir=next_state["workspace_dir"],
        source_type=next_state["source_type"],
        source_url=next_state["source_url"],
        branch=next_state.get("branch"),
    )

    next_state["input_dir"] = str(ingestion_result.input_dir)
    next_state["artifacts_dir"] = str(ingestion_result.artifacts_dir)
    next_state["output_dir"] = str(ingestion_result.output_dir)
    next_state["status"] = "ingesting"
    next_state["current_step"] = "Acquired source code into migration workspace"
    next_state["progress_pct"] = 10
    next_state["logs"] = [
        *next_state["logs"],
        f"Ingested {next_state['source_type']} source into workspace",
    ]
    next_state["metadata"] = {
        **next_state["metadata"],
        "ingestion": ingestion_result.metadata,
    }
    return next_state
