"""Migration planning node — builds the conversion queue for the supervisor."""

from __future__ import annotations

from copy import deepcopy
import re

from app.agents.state import MigrationState
from app.services.migration_planning_service import MigrationPlanningService


def _to_snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _predicted_output_path(component_type: str, component: dict) -> str:
    class_name = str(component.get("class_name", "component"))
    snake = _to_snake(class_name.removesuffix("Impl"))
    if component_type == "model":
        return f"app/models/{snake}.py"
    if component_type == "enum":
        return f"app/models/{snake}.py"
    if component_type == "schema":
        return f"app/schemas/{snake}.py"
    if component_type == "repo":
        return f"app/repositories/{snake}.py"
    if component_type == "service":
        return f"app/services/{snake}.py"
    if component_type == "controller":
        return f"app/api/v1/endpoints/{snake}.py"
    if component_type == "exception_handler":
        return f"app/core/{snake}.py"
    if component_type == "feign_client":
        return f"app/clients/{snake}.py"
    if component_type == "event_consumer":
        return f"app/consumers/{snake}_consumer.py"
    if component_type == "scheduled_task":
        return "app/scheduler.py"
    return ""


def _build_checklist_item(component_type: str, component: dict) -> dict[str, object]:
    class_name = str(component.get("class_name", "component"))
    return {
        "id": f"{component_type}:{class_name}",
        "type": component_type,
        "class_name": class_name,
        "source_file": str(component.get("file_path", "")),
        "target_file": _predicted_output_path(component_type, component),
        "status": "pending",
        "tier": None,
        "error": None,
        "attempts": 0,
    }


async def plan_migration_node(state: MigrationState) -> MigrationState:
    """Generate a migration plan and build the per-component conversion queue."""
    next_state = deepcopy(state)
    docs_references = next_state.get("metadata", {}).get("docs_research", {}).get("references", [])

    result = await MigrationPlanningService().create_plan(
        artifacts_dir=next_state["artifacts_dir"],
        discovered_technologies=next_state["discovered_technologies"],
        business_rules=next_state["business_rules"],
        docs_references=docs_references,
        component_inventory=next_state.get("component_inventory"),
        class_hierarchy=next_state.get("class_hierarchy"),
    )

    # ── Build dependency-ordered conversion queue ──
    inventory = next_state.get("component_inventory", {})
    # Also check metadata for component_inventory (from older pipeline)
    if not inventory:
        inventory = next_state.get("metadata", {}).get("component_inventory", {})

    queue: list[dict] = []
    checklist: list[dict[str, object]] = []
    output_registry: dict[str, str] = {}

    # 1. Models first (no dependencies)
    for entity in inventory.get("entities", []):
        queue.append({"type": "model", "component": entity, "status": "pending"})
        checklist.append(_build_checklist_item("model", entity))
        output_registry[entity["class_name"]] = _predicted_output_path("model", entity)

    # 1b. Enums immediately after models
    for enum_comp in inventory.get("enums", []):
        queue.append({"type": "enum", "component": enum_comp, "status": "pending"})
        checklist.append(_build_checklist_item("enum", enum_comp))
        output_registry[enum_comp["class_name"]] = _predicted_output_path("enum", enum_comp)

    # 2. Schemas second (depend on models for type references)
    for dto in inventory.get("dtos", []):
        queue.append({"type": "schema", "component": dto, "status": "pending"})
        checklist.append(_build_checklist_item("schema", dto))
        output_registry[dto["class_name"]] = _predicted_output_path("schema", dto)

    # 3. Repositories third (depend on models)
    for repo in inventory.get("repositories", []):
        queue.append({"type": "repo", "component": repo, "status": "pending"})
        checklist.append(_build_checklist_item("repo", repo))
        output_registry[repo["class_name"]] = _predicted_output_path("repo", repo)

    # 4. Services fourth (depend on models + schemas + repos)
    for svc in inventory.get("services", []):
        queue.append({"type": "service", "component": svc, "status": "pending"})
        checklist.append(_build_checklist_item("service", svc))
        output_registry[svc["class_name"]] = _predicted_output_path("service", svc)

    # 5. Controllers (depend on services + schemas)
    for ctrl in inventory.get("controllers", []):
        queue.append({"type": "controller", "component": ctrl, "status": "pending"})
        checklist.append(_build_checklist_item("controller", ctrl))
        output_registry[ctrl["class_name"]] = _predicted_output_path("controller", ctrl)

    # 6. Exception handlers (depend on nothing, but run after controllers)
    for eh in inventory.get("exception_handlers", []):
        queue.append({"type": "exception_handler", "component": eh, "status": "pending"})
        checklist.append(_build_checklist_item("exception_handler", eh))
        output_registry[eh["class_name"]] = _predicted_output_path("exception_handler", eh)

    for client in inventory.get("feign_clients", []):
        queue.append({"type": "feign_client", "component": client, "status": "pending"})
        checklist.append(_build_checklist_item("feign_client", client))
        output_registry[client["class_name"]] = _predicted_output_path("feign_client", client)

    for consumer in inventory.get("event_handlers", []):
        queue.append({"type": "event_consumer", "component": consumer, "status": "pending"})
        checklist.append(_build_checklist_item("event_consumer", consumer))
        output_registry[consumer["class_name"]] = _predicted_output_path("event_consumer", consumer)

    if inventory.get("scheduled_tasks"):
        scheduler_component = {
            "class_name": "ApplicationScheduler",
            "tasks": inventory.get("scheduled_tasks", []),
        }
        queue.append({"type": "scheduled_task", "component": scheduler_component, "status": "pending"})
        checklist.append(_build_checklist_item("scheduled_task", scheduler_component))
        output_registry[scheduler_component["class_name"]] = _predicted_output_path("scheduled_task", scheduler_component)

    # 7. Config files (deterministic, handles settings/db/deps)
    queue.append({
        "type": "config",
        "component": {"class_name": "ProjectConfig"},
        "status": "pending",
    })
    checklist.append(_build_checklist_item("config", {"class_name": "ProjectConfig"}))

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
            "per_component_notes": result.per_component_notes,
        },
    }
    next_state["per_component_notes"] = result.per_component_notes

    # ── Set subgraph fields ──
    next_state["conversion_queue"] = queue
    next_state["completed_conversions"] = []
    next_state["failed_conversions"] = []
    next_state["current_conversion"] = None
    next_state["existing_generated_code"] = {}
    next_state["output_registry"] = output_registry
    next_state["migration_checklist"] = checklist

    return next_state
