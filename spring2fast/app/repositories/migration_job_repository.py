"""Persistence helpers for migration job progress — backed by Supabase."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.supabase_client import get_supabase

TABLE = "migration_jobs"


class MigrationJobRepository:
    """Encapsulates job progress persistence via Supabase."""

    def __init__(self) -> None:
        self.db = get_supabase()

    # ── Internal helpers ──────────────────────────────────────────────

    def _update(self, job_id: str, payload: dict[str, Any]) -> None:
        """Synchronous upsert helper (Supabase py client is sync)."""
        self.db.table(TABLE).update(payload).eq("id", job_id).execute()

    # ── Public API ────────────────────────────────────────────────────

    async def update_progress(
        self,
        *,
        job_id: str,
        status: str,
        current_step: str | None,
        progress_pct: int | None = None,
        error_message: str | None = None,
        output_path: str | None = None,
        completed_at: datetime | None = None,
    ) -> None:
        """Update job progress fields in Supabase (called from async context)."""
        import asyncio

        payload: dict[str, Any] = {
            "status": status,
            "current_step": current_step,
            "error_message": error_message,
        }
        if progress_pct is not None:
            payload["progress_pct"] = progress_pct
        if output_path is not None:
            payload["output_path"] = output_path
        if completed_at is not None:
            payload["completed_at"] = completed_at.isoformat()

        # Run the sync Supabase call in a thread so we don't block the event loop
        await asyncio.get_event_loop().run_in_executor(
            None, self._update, job_id, payload
        )
