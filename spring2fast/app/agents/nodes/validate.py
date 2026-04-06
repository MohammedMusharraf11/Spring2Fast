"""Validation node — full-pipeline validation after subgraph completes.

Runs after the migration subgraph has processed ALL components.
Validates the entire generated output directory, not individual chunks.
On failure, sets validation_errors + increments retry_count so the
main graph's condition_after_validate can route back to migrate.
"""

from __future__ import annotations

from copy import deepcopy

from app.agents.state import MigrationState
from app.services.validation_service import ValidationService


async def validate_node(state: MigrationState) -> MigrationState:
    """Validate the full generated project after all conversions complete."""
    next_state = deepcopy(state)

    # Run multi-layer validation on the entire output
    result = await ValidationService().validate(
        output_dir=next_state.get("output_dir", ""),
        artifacts_dir=next_state.get("artifacts_dir", ""),
        business_rules=next_state.get("business_rules", []),
        contracts_dir=next_state.get("contracts_dir"),
        component_inventory=next_state.get("component_inventory"),
    )

    # Count conversion stats for logging
    completed = next_state.get("completed_conversions", [])
    failed = next_state.get("failed_conversions", [])
    total = len(completed) + len(failed)
    passed = sum(1 for c in completed if c.get("passed"))

    if result.is_successful:
        # ── Validation passed ──
        next_state["retry_count"] = 0
        next_state["validation_errors"] = []
        next_state["status"] = "validating"
        next_state["current_step"] = (
            f"Validation passed: {passed}/{total} components, "
            f"all checks OK"
        )
        next_state["progress_pct"] = 90
    else:
        # ── Validation failed — increment retry for conditional edge ──
        next_state["retry_count"] = next_state.get("retry_count", 0) + 1
        next_state["validation_errors"] = result.validation_errors
        next_state["validation_warnings"] = result.warnings
        next_state["checks_passed"] = result.checks_passed

        retry_count = next_state["retry_count"]
        max_retries = 3

        if retry_count < max_retries:
            next_state["status"] = "migrating"
            next_state["current_step"] = (
                f"Validation failed (attempt {retry_count}/{max_retries}), "
                f"retrying migration..."
            )
            # Re-queue failed conversions for retry
            if failed:
                retry_queue = []
                for f_item in failed:
                    retry_queue.append({
                        "type": f_item.get("component_type", "config"),
                        "component": {
                            "class_name": f_item.get("component_name", "Unknown"),
                        },
                        "status": "retry",
                    })
                next_state["conversion_queue"] = retry_queue
                next_state["failed_conversions"] = []

            # Inject error context into logs for the next LLM attempt
            error_summary = "; ".join(result.validation_errors[:5])
            next_state["logs"] = [
                *next_state.get("logs", []),
                f"Retry {retry_count}/{max_retries}: {error_summary}",
            ]
        else:
            # Max retries exhausted — proceed with warnings
            next_state["retry_count"] = 0
            next_state["validation_errors"] = []  # Clear so condition routes to assemble
            next_state["status"] = "validating"
            next_state["current_step"] = (
                f"Validation: {passed}/{total} components OK, "
                f"proceeding after {max_retries} attempts"
            )
            next_state["progress_pct"] = 85

    # Store validation report
    next_state["analysis_artifacts"] = {
        **next_state.get("analysis_artifacts", {}),
        "validation_report": str(result.artifact_path),
    }

    next_state["logs"] = [
        *next_state.get("logs", []),
        f"Validation: {'PASSED' if result.is_successful else 'FAILED'} "
        f"(checks: {result.checks_passed})",
    ]
    return next_state
