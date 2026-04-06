"""Migration planning node — builds the conversion queue for the supervisor."""

from __future__ import annotations

from copy import deepcopy

from app.agents.state import MigrationState
from app.services.migration_planning_service import MigrationPlanningService


def plan_migration_node(state: MigrationState) -> MigrationState:
    """Generate a migration plan and build the per-component conversion queue."""
    next_state = deepcopy(state)
    docs_references = next_state.get("metadata", {}).get("docs_research", {}).get("references", [])

    result = MigrationPlanningService().create_plan(
        artifacts_dir=next_state["artifacts_dir"],
        discovered_technologies=next_state["discovered_technologies"],
        business_rules=next_state["business_rules"],
        docs_references=docs_references,
    )

    # ── Build dependency-ordered conversion queue ──
    inventory = next_state.get("component_inventory", {})
    # Also check metadata for component_inventory (from older pipeline)
    if not inventory:
        inventory = next_state.get("metadata", {}).get("component_inventory", {})

    queue: list[dict] = []

    # 1. Models first (no dependencies)
    for entity in inventory.get("entities", []):
        queue.append({"type": "model", "component": entity, "status": "pending"})

    # 2. Schemas second (depend on models for type references)
    for dto in inventory.get("dtos", []):
        queue.append({"type": "schema", "component": dto, "status": "pending"})

    # 3. Repositories third (depend on models)
    for repo in inventory.get("repositories", []):
        queue.append({"type": "repo", "component": repo, "status": "pending"})

    # 4. Services fourth (depend on models + schemas + repos)
    for svc in inventory.get("services", []):
        queue.append({"type": "service", "component": svc, "status": "pending"})

    # 5. Controllers (depend on services + schemas)
    for ctrl in inventory.get("controllers", []):
        queue.append({"type": "controller", "component": ctrl, "status": "pending"})

    # 6. Exception handlers (depend on nothing, but run after controllers)
    for eh in inventory.get("exception_handlers", []):
        queue.append({"type": "exception_handler", "component": eh, "status": "pending"})

    # 7. Config files (deterministic, handles settings/db/deps)
    queue.append({
        "type": "config",
        "component": {"class_name": "ProjectConfig"},
        "status": "pending",
    })

    next_state["status"] = "planning"
    next_state["current_step"] = "Created migration blueprint and conversion queue"
    next_state["progress_pct"] = 40
    next_state["analysis_artifacts"] = {
        **next_state.get("analysis_artifacts", {}),
        "migration_plan": str(result.artifact_path),
    }
    next_state["logs"] = [
        *next_state.get("logs", []),
        f"Planned {len(result.target_files)} target files, queued {len(queue)} components",
    ]
    next_state["metadata"] = {
        **next_state.get("metadata", {}),
        "migration_plan": {
            "target_files": result.target_files,
            "implementation_steps": result.implementation_steps,
            "risk_items": result.risk_items,
        },
    }

    # ── Set subgraph fields ──
    next_state["conversion_queue"] = queue
    next_state["completed_conversions"] = []
    next_state["failed_conversions"] = []
    next_state["current_conversion"] = None
    next_state["existing_generated_code"] = {}

    return next_state
