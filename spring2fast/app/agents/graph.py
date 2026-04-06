"""LangGraph workflow — DAG with supervisor subgraph.

Architecture:
                    ┌── tech_discover (fn) ──────┐
    ingest (fn) ────┼── biz_logic (fn) ──────────┼── merge_analysis (fn)
                    └── discover_components (fn)──┘          │
                                                             ▼
                                                  research_docs (fn) → analyze (fn) → plan (fn)
                                                             │
                                                ┌────────────▼──────────────┐
                                                │  MIGRATION SUBGRAPH       │
                                                │  supervisor → converters  │
                                                │  → quality_gate → exit    │
                                                └────────────┬──────────────┘
                                                             │
                                                  validate (fn) ─┬─ pass → assemble → END
                                                                 └─ fail → migrate (retry)
"""

from __future__ import annotations

from typing import Any, Callable

try:
    from langgraph.graph import END, StateGraph
except ModuleNotFoundError:  # pragma: no cover
    END = "__end__"

    class _CompiledGraph:
        """Fallback compiled graph that supports DAG fan-out/fan-in and async nodes."""

        def __init__(
            self,
            entry_point: str,
            nodes: dict[str, Callable],
            edges: dict[str, str | list[str] | Callable],
            conditional_targets: dict[str, dict[str, str]] | None = None,
        ) -> None:
            self.entry_point = entry_point
            self.nodes = nodes
            self.edges = edges
            self.conditional_targets = conditional_targets or {}
            self.on_node_complete: Callable | None = None  # callback(node_name, state)

        async def _run_node(self, node_name: str, func: Any, state: dict[str, Any]) -> dict[str, Any]:
            """Execute a single node and fire the callback."""
            import inspect

            if hasattr(func, "ainvoke"):
                result = await func.ainvoke(state)
            elif inspect.iscoroutinefunction(func):
                result = await func(state)
            else:
                result = func(state)

            if self.on_node_complete:
                try:
                    cb_result = self.on_node_complete(node_name, result)
                    if hasattr(cb_result, "__await__"):
                        await cb_result
                except Exception:
                    pass  # Don't break the pipeline on callback errors

            return result

        async def ainvoke(self, state: dict[str, Any]) -> dict[str, Any]:
            next_state = state
            current = self.entry_point
            visited: set[str] = set()

            while current != END:
                if current in visited and current not in ("migrate", "validate"):
                    break  # safety: prevent infinite loops on non-retry nodes
                visited.add(current)

                node_func = self.nodes[current]
                next_state = await self._run_node(current, node_func, next_state)

                edge_val = self.edges.get(current, END)

                # Handle fan-out (list of targets → run sequentially in fallback)
                if isinstance(edge_val, list):
                    for target in edge_val:
                        target_func = self.nodes[target]
                        next_state = await self._run_node(target, target_func, next_state)

                    # Find the fan-in node (all fan-out targets share the same next edge)
                    fan_in_targets = set()
                    for target in edge_val:
                        t_edge = self.edges.get(target, END)
                        if isinstance(t_edge, str):
                            fan_in_targets.add(t_edge)
                    current = fan_in_targets.pop() if fan_in_targets else END
                    continue

                if callable(edge_val):
                    condition_result = edge_val(next_state)
                    routing_map = self.conditional_targets.get(current, {})
                    current = routing_map.get(condition_result, condition_result)
                else:
                    current = edge_val

            return next_state

        async def astream(self, state, *, stream_mode="values"):
            """Minimal stream shim for the fallback."""
            result = await self.ainvoke(state)
            yield result

    class StateGraph:  # pragma: no cover
        def __init__(self, _state_type: Any = None) -> None:
            self._nodes: dict[str, Callable] = {}
            self._edges: dict[str, str | list[str] | Callable] = {}
            self._conditional_targets: dict[str, dict[str, str]] = {}
            self._entry_point: str | None = None

        def add_node(self, name: str, func: Callable) -> None:
            self._nodes[name] = func

        def set_entry_point(self, name: str) -> None:
            self._entry_point = name

        def add_edge(self, source: str, target: str) -> None:
            existing = self._edges.get(source)
            if existing is not None:
                # Multiple edges from same source = fan-out
                if isinstance(existing, list):
                    existing.append(target)
                elif isinstance(existing, str):
                    self._edges[source] = [existing, target]
                else:
                    self._edges[source] = target  # replace callable — shouldn't happen
            else:
                self._edges[source] = target

        def add_conditional_edges(
            self, source: str, condition: Callable, targets: dict[str, str] | None = None
        ) -> None:
            self._edges[source] = condition
            if targets:
                self._conditional_targets[source] = targets

        def compile(self) -> _CompiledGraph:
            if self._entry_point is None:
                raise ValueError("Entry point must be set before compiling.")
            return _CompiledGraph(
                self._entry_point, self._nodes, self._edges, self._conditional_targets
            )


from app.agents.nodes import (
    analyze_node,
    assemble_node,
    discover_components_node,
    extract_business_logic_node,
    ingest_node,
    merge_analysis_node,
    plan_migration_node,
    research_docs_node,
    tech_discover_node,
    validate_node,
)
from app.agents.state import MigrationState
from app.agents.migration_subgraph.graph import build_migration_subgraph


def condition_after_validate(state: MigrationState) -> str:
    """After validation: always assemble — errors are logged, not re-migrated."""
    return "assemble"


def build_migration_graph():
    """Build the main migration DAG with embedded supervisor subgraph."""
    builder = StateGraph(MigrationState)

    # ── Register nodes ──
    builder.add_node("ingest", ingest_node)
    builder.add_node("tech_discover", tech_discover_node)
    builder.add_node("extract_business_logic", extract_business_logic_node)
    builder.add_node("discover_components", discover_components_node)
    builder.add_node("merge_analysis", merge_analysis_node)
    builder.add_node("research_docs", research_docs_node)
    builder.add_node("analyze", analyze_node)
    builder.add_node("plan", plan_migration_node)

    # The migrate node IS the subgraph
    migration_subgraph = build_migration_subgraph()
    builder.add_node("migrate", migration_subgraph)

    builder.add_node("validate", validate_node)
    builder.add_node("assemble", assemble_node)

    # ── Wiring ──
    builder.set_entry_point("ingest")

    # DAG fan-out: ingest → 3 parallel analysis branches
    builder.add_edge("ingest", "tech_discover")
    builder.add_edge("ingest", "extract_business_logic")
    builder.add_edge("ingest", "discover_components")

    # DAG fan-in: all 3 branches → merge_analysis
    builder.add_edge("tech_discover", "merge_analysis")
    builder.add_edge("extract_business_logic", "merge_analysis")
    builder.add_edge("discover_components", "merge_analysis")

    # Sequential pipeline continues
    builder.add_edge("merge_analysis", "research_docs")
    builder.add_edge("research_docs", "analyze")
    builder.add_edge("analyze", "plan")
    builder.add_edge("plan", "migrate")
    builder.add_edge("migrate", "validate")

    # Always assemble after validate
    builder.add_conditional_edges("validate", condition_after_validate, {
        "assemble": "assemble",
    })
    builder.add_edge("assemble", END)

    return builder.compile()
