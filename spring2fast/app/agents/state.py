"""Shared state shape for the migration workflow.

Uses Annotated reducers so parallel DAG branches can merge cleanly.
When LangGraph runs nodes in parallel, each branch returns partial state
updates. The reducers tell LangGraph HOW to combine them.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, NotRequired, TypedDict

# ── Sentinel to distinguish "not provided" from explicit None ──────────────
_MISSING = object()


def _latest_any(a: Any, b: Any) -> Any:
    """Take b if provided (even if None/empty), else keep a.

    NOTE: Uses _MISSING sentinel — DO NOT use this for subgraph fields
    that intentionally set None to signal state transitions.
    """
    return b if b is not None else a


def _always_latest(a: Any, b: Any) -> Any:
    """Always take b — even if b is None, False, [], {}.

    Required for fields that use None/empty as a meaningful signal
    (e.g. current_conversion=None means 'queue is empty').
    """
    return b


def _merge_dicts(a: dict, b: dict) -> dict:
    """Deep-merge two dicts (b wins on conflict)."""
    merged = {**a}
    for k, v in b.items():
        if k in merged and isinstance(merged[k], dict) and isinstance(v, dict):
            merged[k] = _merge_dicts(merged[k], v)
        else:
            merged[k] = v
    return merged


def _latest_str(a: str, b: str) -> str:
    """Take the latest non-empty string."""
    return b if b else a


def _latest_int(a: int, b: int) -> int:
    """Take the higher progress value."""
    return max(a, b)


def _dedupe_list(a: list, b: list) -> list:
    """Concatenate and deduplicate lists while preserving order."""
    seen: set = set()
    result: list = []
    for item in a + b:
        key = str(item)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


class MigrationState(TypedDict):
    """LangGraph state shared across all nodes.

    Fields with Annotated reducers support parallel fan-in from the DAG.
    """

    job_id: Annotated[str, _latest_any]
    source_type: Annotated[Literal["github", "upload", "folder"], _latest_any]
    source_url: Annotated[str, _latest_any]
    branch: Annotated[NotRequired[str | None], _latest_any]
    workspace_dir: Annotated[str, _latest_any]
    input_dir: Annotated[NotRequired[str], _latest_any]
    artifacts_dir: Annotated[NotRequired[str], _latest_any]
    output_dir: Annotated[NotRequired[str], _latest_any]

    # ── Progress tracking (use latest/max values) ──
    status: Annotated[str, _latest_str]
    current_step: Annotated[str, _latest_str]
    progress_pct: Annotated[int, _latest_int]

    # ── Parallel-safe collections (merge on fan-in) ──
    logs: Annotated[list[str], _dedupe_list]
    analysis_artifacts: Annotated[dict[str, str], _merge_dicts]
    discovered_technologies: Annotated[list[str], _dedupe_list]
    business_rules: Annotated[list[str], _dedupe_list]
    generated_files: Annotated[list[str], _dedupe_list]
    validation_errors: Annotated[list[str], _dedupe_list]
    metadata: Annotated[dict[str, Any], _merge_dicts]

    retry_count: Annotated[int, _latest_any]

    # ── Contracts ──
    contracts_dir: Annotated[NotRequired[str], _latest_any]
    business_logic_contracts: Annotated[NotRequired[list[dict[str, str]]], _dedupe_list]

    # ── Inter-layer context for LLM synthesis ──
    existing_generated_code: Annotated[NotRequired[dict[str, str]], _merge_dicts]
    output_registry: Annotated[NotRequired[dict[str, str]], _merge_dicts]

    # ── Validation details ──
    validation_warnings: Annotated[NotRequired[list[str]], _dedupe_list]
    checks_passed: Annotated[NotRequired[dict[str, bool]], _merge_dicts]

    # ── Component inventory ──
    component_inventory: Annotated[NotRequired[dict[str, list[dict[str, Any]]]], _merge_dicts]

    # ── Supervisor subgraph fields ──
    # IMPORTANT: These use _always_latest, NOT _latest_any.
    # The supervisor sets current_conversion=None and conversion_queue=[]
    # as meaningful signals. _latest_any would silently ignore None/[]
    # and keep stale values — causing the supervisor loop to never exit.
    conversion_queue: Annotated[NotRequired[list[dict[str, Any]]], _always_latest]
    completed_conversions: Annotated[NotRequired[list[dict[str, Any]]], _always_latest]
    failed_conversions: Annotated[NotRequired[list[dict[str, Any]]], _always_latest]
    current_conversion: Annotated[NotRequired[dict[str, Any] | None], _always_latest]
