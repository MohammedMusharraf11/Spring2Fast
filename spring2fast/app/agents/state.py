"""Shared state shape for the migration workflow.

Uses Annotated reducers so parallel DAG branches can merge cleanly.
When LangGraph runs nodes in parallel, each branch returns partial state
updates. The reducers tell LangGraph HOW to combine them.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, NotRequired, TypedDict


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

    job_id: str
    source_type: Literal["github", "upload", "folder"]
    source_url: str
    branch: NotRequired[str | None]
    workspace_dir: str
    input_dir: NotRequired[str]
    artifacts_dir: NotRequired[str]
    output_dir: NotRequired[str]

    # ── Progress tracking (use latest/max values) ──
    status: Annotated[str, _latest_str]
    current_step: Annotated[str, _latest_str]
    progress_pct: Annotated[int, _latest_int]

    # ── Parallel-safe collections (merge on fan-in) ──
    logs: Annotated[list[str], operator.add]
    analysis_artifacts: Annotated[dict[str, str], _merge_dicts]
    discovered_technologies: Annotated[list[str], _dedupe_list]
    business_rules: Annotated[list[str], _dedupe_list]
    generated_files: Annotated[list[str], _dedupe_list]
    validation_errors: Annotated[list[str], operator.add]
    metadata: Annotated[dict[str, Any], _merge_dicts]

    retry_count: int

    # ── Contracts ──
    contracts_dir: NotRequired[str]
    business_logic_contracts: NotRequired[list[dict[str, str]]]

    # ── Inter-layer context for LLM synthesis ──
    existing_generated_code: NotRequired[dict[str, str]]

    # ── Validation details ──
    validation_warnings: NotRequired[list[str]]
    checks_passed: NotRequired[dict[str, bool]]

    # ── Component inventory ──
    component_inventory: NotRequired[dict[str, list[dict[str, Any]]]]

    # ── Supervisor subgraph fields ──
    conversion_queue: NotRequired[list[dict[str, Any]]]
    completed_conversions: NotRequired[list[dict[str, Any]]]
    failed_conversions: NotRequired[list[dict[str, Any]]]
    current_conversion: NotRequired[dict[str, Any] | None]
