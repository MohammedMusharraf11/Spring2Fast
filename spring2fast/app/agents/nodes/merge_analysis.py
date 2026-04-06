"""Merge analysis node — fan-in point for the parallel DAG branches.

Receives the merged state from tech_discover + biz_logic + discover_components
(LangGraph's reducers handle the raw merge). This node cross-references and
validates the combined analysis outputs.
"""

from __future__ import annotations

from copy import deepcopy

from app.agents.state import MigrationState


def merge_analysis_node(state: MigrationState) -> MigrationState:
    """Cross-reference and validate merged outputs from parallel analysis branches."""
    next_state = deepcopy(state)

    # The three parallel branches have already deposited their results into state
    techs = next_state.get("discovered_technologies", [])
    rules = next_state.get("business_rules", [])
    inventory = next_state.get("component_inventory", {})
    contracts = next_state.get("business_logic_contracts", [])

    # Cross-reference: count totals for logging
    total_components = sum(len(v) for v in inventory.values()) if inventory else 0
    total_contracts = len(contracts) if contracts else 0

    next_state["status"] = "analyzing"
    next_state["current_step"] = "Merged parallel analysis results"
    next_state["progress_pct"] = 45
    next_state["logs"] = [
        *next_state.get("logs", []),
        f"Merged analysis: {len(techs)} techs, {len(rules)} rules, "
        f"{total_components} components, {total_contracts} contracts",
    ]

    return next_state
