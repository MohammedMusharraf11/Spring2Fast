"""Runs the migration graph for a job request.

The orchestrator delegates ALL graph traversal to the compiled graph's
own `ainvoke()` method which handles DAG fan-out/fan-in, subgraphs,
async nodes, and conditional edges. The orchestrator only manages
state persistence and DB progress updates.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from app.agents.graph import build_migration_graph
from app.agents.state import MigrationState
from app.config import settings
from app.repositories.migration_job_repository import MigrationJobRepository


class MigrationOrchestrator:
    """Thin orchestration layer around the LangGraph workflow."""

    def __init__(self) -> None:
        self.graph = build_migration_graph()
        self.job_repository = MigrationJobRepository()

    def _persist_state(self, state: MigrationState) -> None:
        """Persist the current migration state to a JSON file for frontend access."""
        artifacts_dir = state.get("artifacts_dir")
        if not artifacts_dir:
            return

        state_file = Path(artifacts_dir) / "_state.json"
        state_file.parent.mkdir(parents=True, exist_ok=True)

        serializable = {}
        for key, value in state.items():
            if isinstance(value, Path):
                serializable[key] = str(value)
            else:
                serializable[key] = value

        try:
            state_file.write_text(
                json.dumps(serializable, indent=2, default=str),
                encoding="utf-8",
            )
        except Exception:
            pass  # Non-critical

    async def run_migration(
        self,
        *,
        job_id: str,
        source_type: str,
        source_url: str | None = None,
        branch: str | None = None,
    ) -> MigrationState:
        """Run the full migration workflow via the compiled graph."""
        if not source_url:
            raise ValueError("source_url is required to run a migration job.")

        initial_state: MigrationState = {
            "job_id": job_id,
            "source_type": source_type,
            "source_url": source_url,
            "branch": branch,
            "workspace_dir": str(settings.workspace_path),
            "status": "pending",
            "current_step": "Job created",
            "progress_pct": 0,
            "logs": [],
            "analysis_artifacts": {},
            "discovered_technologies": [],
            "business_rules": [],
            "generated_files": [],
            "validation_errors": [],
            "retry_count": 0,
            "metadata": {},
        }

        await self.job_repository.update_progress(
            job_id=job_id,
            status="ingesting",
            current_step="Starting migration workflow",
            progress_pct=1,
        )

        last_state = initial_state

        try:
            # Use astream to get per-node state updates (works with real LangGraph).
            # This lets us persist state + update DB after every node completes,
            # giving the frontend real-time progress updates.
            try:
                async for chunk in self.graph.astream(
                    initial_state,
                    stream_mode="values",
                    config={"recursion_limit": 200},
                ):
                    # Each chunk is the full state after a node completes
                    if isinstance(chunk, dict):
                        last_state = chunk
                        self._persist_state(chunk)
                        await self.job_repository.update_progress(
                            job_id=job_id,
                            status=chunk.get("status", "ingesting"),
                            current_step=chunk.get("current_step", "Processing..."),
                            progress_pct=chunk.get("progress_pct", 0),
                        )
                final_state = last_state
            except (NotImplementedError, TypeError, AttributeError):
                # Fallback for graph implementations without astream
                final_state = await self.graph.ainvoke(initial_state)
                last_state = final_state

            # Persist final state
            self._persist_state(final_state)

            # Update progress from completed conversions if available
            completed = final_state.get("completed_conversions", [])
            failed = final_state.get("failed_conversions", [])
            if completed or failed:
                total = len(completed) + len(failed)
                passed = sum(1 for c in completed if c.get("passed"))
                final_state["logs"] = [
                    *final_state.get("logs", []),
                    f"Pipeline complete: {passed}/{total} components converted",
                ]

        except Exception as exc:
            if last_state and "logs" in last_state:
                last_state["logs"].append(f"CRITICAL ERROR: {str(exc)}")

            if last_state and "artifacts_dir" not in last_state:
                artifacts_dir = Path(settings.workspace_path) / job_id / "artifacts"
                artifacts_dir.mkdir(parents=True, exist_ok=True)
                last_state["artifacts_dir"] = str(artifacts_dir)

            if last_state:
                self._persist_state(last_state)

            await self.job_repository.update_progress(
                job_id=job_id,
                status="failed",
                current_step="Migration workflow failed",
                error_message=str(exc),
            )
            raise

        await self.job_repository.update_progress(
            job_id=job_id,
            status=final_state.get("status", "completed"),
            current_step=final_state.get("current_step", "Done"),
            progress_pct=final_state.get("progress_pct", 100),
            error_message=None,
            output_path=final_state.get("metadata", {}).get("output_zip"),
            completed_at=datetime.utcnow() if final_state.get("status") == "completed" else None,
        )
        return final_state
