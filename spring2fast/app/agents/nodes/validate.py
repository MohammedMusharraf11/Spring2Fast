"""Validation node — lightweight pass after migration subgraph completes.

Strategy: run validation ONCE, log any errors, always proceed to assemble.
The user wants ALL code migrated — we don't re-migrate on validation failure,
we just report what passed/failed and package everything.
"""

from __future__ import annotations

from copy import deepcopy

from app.agents.state import MigrationState
from app.services.validation_service import ValidationService


async def validate_node(state: MigrationState) -> MigrationState:
    """Validate generated output — logs results, always proceeds to assemble."""
    next_state = deepcopy(state)

    output_dir = next_state.get("output_dir", "")
    artifacts_dir = next_state.get("artifacts_dir", "")

    if not output_dir:
        next_state["status"] = "validating"
        next_state["current_step"] = "Validation skipped (no output dir)"
        next_state["progress_pct"] = 92
        return next_state

    try:
        result = await ValidationService().validate(
            output_dir=output_dir,
            artifacts_dir=artifacts_dir,
            business_rules=next_state.get("business_rules", []),
            contracts_dir=next_state.get("contracts_dir"),
            component_inventory=next_state.get("component_inventory"),
        )

        completed = next_state.get("completed_conversions", [])
        failed = next_state.get("failed_conversions", [])
        total = len(completed) + len(failed)
        passed = sum(1 for c in completed if c.get("passed"))

        # Always proceed — no re-migration loops
        next_state["validation_errors"] = result.validation_errors
        next_state["validation_warnings"] = result.warnings if hasattr(result, "warnings") else []
        next_state["checks_passed"] = result.checks_passed
        next_state["status"] = "validating"
        next_state["progress_pct"] = 92

        status_str = "PASSED" if result.is_successful else f"{len(result.validation_errors)} warnings"
        next_state["current_step"] = (
            f"Validation complete: {passed}/{total} components — {status_str}"
        )
        next_state["logs"] = [
            *next_state.get("logs", []),
            f"✅ Validation: {passed}/{total} components converted ({status_str})",
        ]

        if result.validation_errors:
            next_state["logs"] = [
                *next_state["logs"],
                *[f"⚠️ {e}" for e in result.validation_errors[:10]],
            ]

        next_state["analysis_artifacts"] = {
            **next_state.get("analysis_artifacts", {}),
            "validation_report": str(result.artifact_path),
        }

    except Exception as exc:
        # Validation errors should never block packaging
        next_state["status"] = "validating"
        next_state["current_step"] = "Validation skipped (error)"
        next_state["progress_pct"] = 92
        next_state["logs"] = [
            *next_state.get("logs", []),
            f"⚠️ Validation error (non-fatal): {exc}",
        ]

    return next_state
