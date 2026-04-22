"""Validation node — lightweight pass after migration subgraph completes.

Strategy: run validation ONCE, log results, always proceed to assemble.
We never block packaging on validation failure — just report and continue.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

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
        )

        completed = next_state.get("completed_conversions", [])
        failed = next_state.get("failed_conversions", [])
        total = len(completed) + len(failed)
        passed = sum(1 for c in completed if c.get("passed"))

        next_state["validation_errors"] = result.validation_errors
        next_state["validation_warnings"] = result.warnings
        next_state["checks_passed"] = result.checks_passed
        next_state["status"] = "validating"
        next_state["progress_pct"] = 92

        if result.is_successful:
            status_str = "PASSED"
        elif result.validation_errors:
            status_str = f"{len(result.validation_errors)} error(s)"
        else:
            status_str = f"{len(result.warnings)} import warning(s)"

        next_state["current_step"] = (
            f"Validation complete: {passed}/{total} components — {status_str}"
        )
        next_state["logs"] = [
            *next_state.get("logs", []),
            f"✅ Validation: {passed}/{total} components converted — {status_str}",
        ]

        # Surface errors and warnings in logs (cap at 10 each)
        if result.validation_errors:
            next_state["logs"] = [
                *next_state["logs"],
                *[f"❌ {e}" for e in result.validation_errors[:10]],
            ]
        if result.warnings:
            next_state["logs"] = [
                *next_state["logs"],
                *[f"⚠️ {w}" for w in result.warnings[:10]],
            ]

        next_state["analysis_artifacts"] = {
            **next_state.get("analysis_artifacts", {}),
            "validation_report": str(result.artifact_path),
        }

        checklist = next_state.get("migration_checklist", [])
        failed_items = [item for item in checklist if item.get("status") == "failed"]
        missing_files: list[str] = []
        for item in checklist:
            target_file = str(item.get("target_file", ""))
            if item.get("status") == "done" and target_file:
                if not (Path(output_dir) / target_file).exists():
                    missing_files.append(target_file)

        if failed_items or missing_files:
            next_state["logs"] = [
                *next_state["logs"],
                f"Checklist: {len(failed_items)} failed, {len(missing_files)} missing files",
                *[
                    f"  FAILED: {item.get('class_name')} ({item.get('error')})"
                    for item in failed_items[:5]
                ],
                *[f"  MISSING: {path}" for path in missing_files[:5]],
            ]

    except Exception as exc:
        # Validation must never block packaging
        next_state["status"] = "validating"
        next_state["current_step"] = "Validation skipped (error)"
        next_state["progress_pct"] = 92
        next_state["logs"] = [
            *next_state.get("logs", []),
            f"⚠️ Validation error (non-fatal): {exc}",
        ]

    return next_state
