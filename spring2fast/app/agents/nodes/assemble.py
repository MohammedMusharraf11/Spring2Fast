"""Final assembly node for the scaffolded workflow."""

from __future__ import annotations

from copy import deepcopy

from app.agents.state import MigrationState


def assemble_node(state: MigrationState) -> MigrationState:
    """Finalize migration and package the output into a ZIP file."""
    import shutil
    from pathlib import Path
    
    next_state = deepcopy(state)
    output_dir = Path(next_state["output_dir"])
    artifacts_dir = Path(next_state["artifacts_dir"])
    
    zip_filename = f"fastapi_project_{next_state['job_id'][:8]}.zip"
    zip_path = artifacts_dir / zip_filename
    
    if output_dir.exists():
        # Create ZIP without leading 'output/' folder
        shutil.make_archive(str(zip_path.with_suffix("")), "zip", str(output_dir))
        
    next_state["status"] = "completed"
    next_state["current_step"] = "Successfully migrated and packaged FastAPI project"
    next_state["progress_pct"] = 100
    next_state["metadata"] = {
        **next_state.get("metadata", {}),
        "output_zip": str(zip_path),
    }
    next_state["logs"] = [
        *next_state["logs"], 
        f"Generated {len(next_state.get('generated_files', []))} files",
        f"Packaged result into {zip_filename}"
    ]
    return next_state
