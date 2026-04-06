"""Final assembly node — post-processes output and optionally pushes to GitHub."""

from __future__ import annotations

import re
from copy import deepcopy
from pathlib import Path

from app.agents.state import MigrationState


_PLACEHOLDER_PACKAGES = re.compile(
    r'\b(yourapp|myapp|your_app|my_app|application|project)\b'
)


def _sanitize_output_dir(output_dir: Path) -> int:
    """Replace placeholder package names in all generated .py files.

    Returns number of files fixed.
    """
    fixed = 0
    for py_file in output_dir.rglob("*.py"):
        try:
            original = py_file.read_text(encoding="utf-8", errors="ignore")
            cleaned = _PLACEHOLDER_PACKAGES.sub("app", original)
            if cleaned != original:
                py_file.write_text(cleaned, encoding="utf-8")
                fixed += 1
        except Exception:
            pass
    return fixed


def assemble_node(state: MigrationState) -> MigrationState:
    """Post-process output, package as ZIP, mark job completed."""
    import shutil

    next_state = deepcopy(state)
    output_dir = Path(next_state["output_dir"])
    artifacts_dir = Path(next_state["artifacts_dir"])

    logs = list(next_state.get("logs", []))

    # ── Step 1: Sanitize placeholder imports across all .py files ──
    if output_dir.exists():
        fixed_count = _sanitize_output_dir(output_dir)
        if fixed_count:
            logs.append(f"🔧 Fixed placeholder imports in {fixed_count} files")

    # ── Step 2: Package as ZIP ──
    zip_filename = f"fastapi_project_{next_state['job_id'][:8]}.zip"
    zip_path = artifacts_dir / zip_filename

    if output_dir.exists():
        shutil.make_archive(str(zip_path.with_suffix("")), "zip", str(output_dir))

    next_state["status"] = "completed"
    next_state["current_step"] = "Successfully migrated and packaged FastAPI project"
    next_state["progress_pct"] = 100
    next_state["metadata"] = {
        **next_state.get("metadata", {}),
        "output_zip": str(zip_path),
        "output_dir": str(output_dir),
    }
    logs.append(f"Generated {len(next_state.get('generated_files', []))} files")
    logs.append(f"Packaged result into {zip_filename}")
    next_state["logs"] = logs
    return next_state
