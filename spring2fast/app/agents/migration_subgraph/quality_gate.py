"""Quality gate — checks conversion results and handles retry routing.

After all components have been through a converter, the quality gate
checks how many passed/failed. Failed components can be re-queued
for one more attempt before the subgraph exits.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.agents.state import MigrationState


MAX_SUBGRAPH_RETRIES = 2


def quality_gate_node(state: MigrationState) -> MigrationState:
    """Evaluate conversion results and decide to exit or retry failures."""
    next_state = deepcopy(state)
    completed = next_state.get("completed_conversions", [])
    failed = next_state.get("failed_conversions", [])
    retry_count = next_state.get("retry_count", 0)

    passed_count = sum(1 for c in completed if c.get("passed"))
    failed_count = len(failed)
    total = passed_count + failed_count

    next_state["logs"] = [
        *next_state.get("logs", []),
        f"Quality gate: {passed_count}/{total} conversions passed, "
        f"{failed_count} failed (retry #{retry_count})",
    ]

    if not failed or retry_count >= MAX_SUBGRAPH_RETRIES:
        # Exit: either all passed or retries exhausted
        next_state["current_step"] = (
            f"Migration complete: {passed_count}/{total} components converted"
        )
        progress_base = 40
        next_state["progress_pct"] = progress_base + int(40 * (passed_count / max(total, 1)))

        # Collect all generated file paths
        all_files = [c.get("output_path", "") for c in completed if c.get("output_path")]
        next_state["generated_files"] = list(set(
            next_state.get("generated_files", []) + all_files
        ))

        if failed:
            next_state["logs"] = [
                *next_state.get("logs", []),
                f"WARNING: {failed_count} components failed conversion after "
                f"{MAX_SUBGRAPH_RETRIES} retries: "
                + ", ".join(f.get("component_name", "?") for f in failed),
            ]
    else:
        # Re-queue failed components for retry
        retry_queue = []
        for f in failed:
            attempts = f.get("attempts", 0)
            if attempts < 3:
                retry_queue.append({
                    "type": f.get("component_type", "config"),
                    "component": {"class_name": f.get("component_name", "?"), **f},
                    "status": "retry",
                })

        next_state["conversion_queue"] = retry_queue
        next_state["failed_conversions"] = []
        next_state["retry_count"] = retry_count + 1
        next_state["current_step"] = f"Retrying {len(retry_queue)} failed conversions"

    return next_state


def should_exit_subgraph(state: MigrationState) -> str:
    """Conditional edge: exit subgraph or retry failed components."""
    failed = state.get("failed_conversions", [])
    retry_count = state.get("retry_count", 0)

    if not failed or retry_count >= MAX_SUBGRAPH_RETRIES:
        return "exit"
    return "retry"
