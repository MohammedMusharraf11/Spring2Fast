"""Migration supervisor — routes components to the correct converter agent.

The supervisor pops the next component from the conversion queue and
decides which converter agent should handle it based on component type.
This is a pure FUNCTION (not an agent) — routing is deterministic.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.agents.state import MigrationState
from app.agents.tools import converter_tools as tools


def supervisor_node(state: MigrationState) -> MigrationState:
    """Pick the next component from the queue and prepare routing state."""
    next_state = deepcopy(state)
    queue = next_state.get("conversion_queue", [])

    if not queue:
        next_state["current_conversion"] = None
        return next_state

    # Pop the next component
    current = queue[0]
    remaining = queue[1:]

    next_state["current_conversion"] = current
    next_state["conversion_queue"] = remaining

    comp_name = current.get("component", {}).get("class_name", "?")
    comp_type = current.get("type", "?")
    next_state["current_step"] = f"Converting {comp_name} ({comp_type})"

    # Update existing_generated_code context from already-written files
    output_dir = next_state.get("output_dir", "")
    if output_dir:
        existing = next_state.get("existing_generated_code", {})
        for layer in ["models", "schemas", "repositories", "services", "controllers"]:
            code = tools.read_existing_code(layer, output_dir)
            if code and not code.startswith("# No"):
                existing[layer] = code
        next_state["existing_generated_code"] = existing

    next_state["logs"] = [
        *next_state.get("logs", []),
        f"Supervisor: routing {comp_name} to {comp_type}_converter "
        f"({len(remaining)} remaining in queue)",
    ]

    return next_state


def route_to_converter(state: MigrationState) -> str:
    """Conditional edge: route to the correct converter or quality gate."""
    current = state.get("current_conversion")
    if not current:
        return "quality_gate"

    comp_type = current.get("type", "")
    converter_map = {
        "model": "model_converter",
        "schema": "schema_converter",
        "repo": "repo_converter",
        "service": "service_converter",
        "controller": "controller_converter",
        "exception_handler": "exception_converter",
        "feign_client": "feign_converter",
        "event_consumer": "event_consumer_converter",
        "scheduled_task": "scheduler_converter",
        "config": "config_converter",
    }
    return converter_map.get(comp_type, "config_converter")
