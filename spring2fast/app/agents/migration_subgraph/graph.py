"""Migration subgraph — supervisor + converter agents + quality gate.

This is a LangGraph subgraph that is embedded into the main migration
graph as the "migrate" node. It processes each component individually
through specialized converter agents.

Architecture:
    supervisor → route_to_converter → [model|schema|repo|service|controller|config]_converter
                                                      ↓
    supervisor ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ┘
        ↓ (queue empty)
    quality_gate → exit or retry
"""

from __future__ import annotations

from typing import Any, Callable

try:
    from langgraph.graph import END, StateGraph
except ModuleNotFoundError:
    END = "__end__"

    class _CompiledGraph:
        def __init__(self, entry_point, nodes, edges, conditional_targets=None):
            self.entry_point = entry_point
            self.nodes = nodes
            self.edges = edges
            self.conditional_targets = conditional_targets or {}

        async def ainvoke(self, state):
            import inspect
            current = self.entry_point
            next_state = state
            while current != END:
                node_func = self.nodes[current]
                if inspect.iscoroutinefunction(node_func):
                    next_state = await node_func(next_state)
                else:
                    next_state = node_func(next_state)
                edge_val = self.edges.get(current, END)
                if callable(edge_val):
                    result = edge_val(next_state)
                    routing = self.conditional_targets.get(current, {})
                    current = routing.get(result, result)
                else:
                    current = edge_val
            return next_state

    class StateGraph:
        def __init__(self, _state_type=None):
            self._nodes = {}
            self._edges = {}
            self._conditional_targets = {}
            self._entry_point = None

        def add_node(self, name, func):
            self._nodes[name] = func

        def set_entry_point(self, name):
            self._entry_point = name

        def add_edge(self, source, target):
            self._edges[source] = target

        def add_conditional_edges(self, source, condition, targets=None):
            self._edges[source] = condition
            if targets:
                self._conditional_targets[source] = targets

        def compile(self):
            return _CompiledGraph(
                self._entry_point, self._nodes, self._edges, self._conditional_targets
            )

from app.agents.state import MigrationState
from app.agents.migration_subgraph.supervisor import supervisor_node, route_to_converter
from app.agents.migration_subgraph.quality_gate import quality_gate_node, should_exit_subgraph
from app.agents.migration_subgraph.converter_nodes import (
    model_converter_node,
    schema_converter_node,
    repo_converter_node,
    service_converter_node,
    controller_converter_node,
    exception_converter_node,
    feign_converter_node,
    event_consumer_converter_node,
    scheduler_converter_node,
    config_converter_node,
)


def build_migration_subgraph():
    """Build the migration supervisor subgraph."""
    builder = StateGraph(MigrationState)

    # ── Nodes ──
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("model_converter", model_converter_node)
    builder.add_node("schema_converter", schema_converter_node)
    builder.add_node("repo_converter", repo_converter_node)
    builder.add_node("service_converter", service_converter_node)
    builder.add_node("controller_converter", controller_converter_node)
    builder.add_node("exception_converter", exception_converter_node)
    builder.add_node("feign_converter", feign_converter_node)
    builder.add_node("event_consumer_converter", event_consumer_converter_node)
    builder.add_node("scheduler_converter", scheduler_converter_node)
    builder.add_node("config_converter", config_converter_node)
    builder.add_node("quality_gate", quality_gate_node)

    # ── Entry ──
    builder.set_entry_point("supervisor")

    # ── Supervisor routes to the correct converter ──
    builder.add_conditional_edges("supervisor", route_to_converter, {
        "model_converter": "model_converter",
        "schema_converter": "schema_converter",
        "repo_converter": "repo_converter",
        "service_converter": "service_converter",
        "controller_converter": "controller_converter",
        "exception_converter": "exception_converter",
        "feign_converter": "feign_converter",
        "event_consumer_converter": "event_consumer_converter",
        "scheduler_converter": "scheduler_converter",
        "config_converter": "config_converter",
        "quality_gate": "quality_gate",
    })

    # ── All converters route back to supervisor ──
    for converter in [
        "model_converter", "schema_converter", "repo_converter",
        "service_converter", "controller_converter", "exception_converter",
        "feign_converter", "event_consumer_converter", "scheduler_converter",
        "config_converter",
    ]:
        builder.add_edge(converter, "supervisor")

    # ── Quality gate: exit or retry ──
    builder.add_conditional_edges("quality_gate", should_exit_subgraph, {
        "exit": END,
        "retry": "supervisor",
    })

    return builder.compile()
