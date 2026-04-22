"""Quality gate — checks conversion results and handles retry routing.

After all components have been through a converter, the quality gate
checks how many passed/failed. Failed components can be re-queued
for one more attempt before the subgraph exits.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import re
from typing import Any

from app.agents.state import MigrationState


MAX_SUBGRAPH_RETRIES = 2


def _rebuild_package_inits(output_dir: str) -> None:
    """Auto-populate generated package __init__.py files."""
    packages = {
        "app/models": True,
        "app/schemas": True,
        "app/services": False,
        "app/repositories": False,
    }
    root = Path(output_dir)

    for rel_pkg, do_exports in packages.items():
        pkg_dir = root / rel_pkg
        if not pkg_dir.exists():
            continue

        exports: list[str] = []
        if do_exports:
            module_path = rel_pkg.replace("/", ".")
            exported_names: list[str] = []
            for py_file in sorted(pkg_dir.glob("*.py")):
                if py_file.stem == "__init__":
                    continue
                try:
                    src = py_file.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                class_names = re.findall(r"^class\s+([A-Z][A-Za-z0-9_]+)", src, re.MULTILINE)
                for cls in class_names:
                    exports.append(f"from {module_path}.{py_file.stem} import {cls}")
                    exported_names.append(cls)
            if exported_names:
                exports.extend(
                    [
                        "",
                        "__all__ = [" + ", ".join(f'"{name}"' for name in exported_names) + "]",
                    ]
                )

        (pkg_dir / "__init__.py").write_text(
            "\n".join(exports) + ("\n" if exports else ""),
            encoding="utf-8",
        )


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
        output_dir = next_state.get("output_dir", "")
        if output_dir:
            _rebuild_package_inits(output_dir)
        next_state["current_step"] = (
            f"Code Generation complete ({passed_count}/{total}). Starting Validation..."
        )
        next_state["status"] = "validating"
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
        # Re-queue failed components for retry. Converter "attempts" tracks the
        # inner self-repair loop, while retry_count tracks subgraph retries.
        retry_queue = []
        for f in failed:
            retry_queue.append({
                "type": f.get("component_type", "config"),
                "component": f.get(
                    "original_component",
                    {"class_name": f.get("component_name", "?")},
                ),
                "status": "retry",
            })

        next_state["conversion_queue"] = retry_queue
        next_state["failed_conversions"] = []
        next_state["retry_count"] = retry_count + 1
        next_state["current_step"] = f"Retrying {len(retry_queue)} failed conversions"
        next_state["status"] = "migrating"

    return next_state


def should_exit_subgraph(state: MigrationState) -> str:
    """Conditional edge: exit subgraph or retry failed components."""
    # Check if we queued anything to retry
    queue = state.get("conversion_queue", [])
    
    if queue:
        return "retry"
    return "exit"
