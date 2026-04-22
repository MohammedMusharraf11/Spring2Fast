"""Component discovery node — discovers Spring components and generates contracts."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import re

from app.agents.state import MigrationState
from app.services.component_discovery_service import ComponentDiscoveryService
from app.services.business_logic_contract_service import BusinessLogicContractService


def _default_table_name(class_name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", class_name).lower() + "s"


def _find_pk_field(entity: dict) -> str:
    for field in entity.get("all_fields") or entity.get("fields") or []:
        annotations = field.get("annotations") or []
        annotation_names = [
            annotation.get("name", "") if isinstance(annotation, dict) else str(annotation).lstrip("@")
            for annotation in annotations
        ]
        if "Id" in annotation_names or "@Id" in annotation_names:
            return str(field.get("name", "id"))
    return "id"


def _find_fk_references(entity: dict) -> str:
    refs: list[str] = []
    for field in entity.get("all_fields") or entity.get("fields") or []:
        annotations = field.get("annotations") or []
        annotation_names = [
            annotation.get("name", "") if isinstance(annotation, dict) else str(annotation).lstrip("@")
            for annotation in annotations
        ]
        if any(name in {"ManyToOne", "OneToOne", "JoinColumn"} for name in annotation_names):
            refs.append(f"{field.get('name')}:{field.get('type')}")
    return ", ".join(refs) if refs else "none"


def _build_class_hierarchy_dict(components: dict) -> dict:
    entities = components.get("entities", [])
    enums = components.get("enums", [])
    controllers = components.get("controllers", [])
    return {
        "entities": [
            {
                "class_name": entity.get("class_name"),
                "extends": entity.get("extends"),
                "superclass_chain": entity.get("superclass_chain", []),
                "table_name": entity.get("table_name"),
                "inheritance_strategy": entity.get("inheritance_strategy"),
                "inherited_fields": entity.get("inherited_fields", []),
                "primary_key": _find_pk_field(entity),
                "foreign_keys": _find_fk_references(entity),
            }
            for entity in entities
        ],
        "enums": [
            {
                "class_name": enum_item.get("class_name"),
                "enum_values": enum_item.get("enum_values", []),
                "file_path": enum_item.get("file_path"),
            }
            for enum_item in enums
        ],
        "shared_dependencies": {
            "get_db": "app/db/session.py",
            "get_current_user": "app/core/security.py"
            if any(
                "httpsession" in str(controller.get("method_details", [])).lower()
                or "session" in str(controller.get("fields", [])).lower()
                for controller in controllers
            )
            else None,
        },
    }


def _build_call_flow_dict(components: dict) -> dict:
    controllers = []
    for ctrl in components.get("controllers", []):
        methods = []
        for method in ctrl.get("method_details", []):
            http_method = "GET"
            route = "/"
            for mapping in method.get("mapping_annotations", []):
                if "Post" in mapping:
                    http_method = "POST"
                elif "Put" in mapping:
                    http_method = "PUT"
                elif "Delete" in mapping:
                    http_method = "DELETE"
                elif "Patch" in mapping:
                    http_method = "PATCH"
                route_match = re.search(r'"([^"]+)"', mapping)
                if route_match:
                    route = route_match.group(1)
            methods.append(
                {
                    "name": method.get("name", ""),
                    "http_method": http_method,
                    "route": route,
                    "service_calls": ctrl.get("service_calls", []),
                }
            )
        controllers.append(
            {
                "class_name": ctrl.get("class_name"),
                "dependencies": ctrl.get("dependencies", []),
                "methods": methods,
            }
        )

    services = [
        {
            "class_name": svc.get("class_name"),
            "dependencies": svc.get("fields", []),
        }
        for svc in components.get("services", [])
    ]
    return {"controllers": controllers, "services": services}


def _generate_class_hierarchy_artifact(components: dict, artifacts_dir: str) -> Path:
    lines = ["# Class Hierarchy & Database Schema", ""]
    lines.append("## Inheritance Chains")
    entities = components.get("entities", [])
    if entities:
        for entity in entities:
            chain = entity.get("superclass_chain", [])
            if chain:
                extends = entity.get("extends", "")
                lines.append(
                    f"- **{entity['class_name']}** extends `{extends}` "
                    f"(chain: {' -> '.join(chain)} -> {entity['class_name']})"
                )
                for field in entity.get("inherited_fields", []):
                    annotations = field.get("annotations") or []
                    annotation_names = [
                        annotation.get("name", "") if isinstance(annotation, dict) else str(annotation).lstrip("@")
                        for annotation in annotations
                    ]
                    pk = " [PK]" if "Id" in annotation_names else ""
                    lines.append(f"  - inherited: `{field['name']}`: {field['type']}{pk}")
            else:
                lines.append(f"- **{entity['class_name']}** has no mapped superclass chain")
    else:
        lines.append("- none discovered")
    lines.append("")

    lines.append("## Enums")
    enums = components.get("enums", [])
    if enums:
        lines.append("| Enum | Values | Source File |")
        lines.append("|------|--------|------------|")
        for enum_item in enums:
            values = ", ".join(enum_item.get("enum_values", []))
            lines.append(f"| {enum_item['class_name']} | {values} | {enum_item['file_path']} |")
    else:
        lines.append("- none discovered")
    lines.append("")

    lines.append("## Database Tables")
    lines.append("| Entity | Table Name | PK Field | Inheritance | FK References |")
    lines.append("|--------|-----------|----------|-------------|---------------|")
    for entity in entities:
        table = entity.get("table_name") or _default_table_name(str(entity["class_name"]))
        pk = _find_pk_field(entity)
        inheritance = entity.get("inheritance_strategy") or "none"
        fks = _find_fk_references(entity)
        lines.append(f"| {entity['class_name']} | {table} | {pk} | {inheritance} | {fks} |")
    lines.append("")

    lines.append("## Shared Dependencies (needed by all endpoints)")
    lines.append("- `get_db` - async database session factory (must be in `app/db/session.py`)")
    uses_auth = any(
        "httpsession" in str(controller.get("method_details", [])).lower()
        or "session" in str(controller.get("fields", [])).lower()
        for controller in components.get("controllers", [])
    )
    if uses_auth:
        lines.append("- `get_current_user` - auth dependency (must be in `app/core/security.py`)")

    artifact_path = Path(artifacts_dir) / "03b-class-hierarchy-db-schema.md"
    artifact_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return artifact_path


def _generate_call_flow_artifact(components: dict, artifacts_dir: str) -> Path:
    lines = ["# Call Flow & Dependency Graph", ""]
    lines.append("## Controller -> Service -> Repository Chain")
    lines.append("| Controller | Method | HTTP | Route | Calls Service Method |")
    lines.append("|-----------|--------|------|-------|---------------------|")

    for ctrl in components.get("controllers", []):
        service_calls = ctrl.get("service_calls", [])
        for method in ctrl.get("method_details", []):
            http_method = "GET"
            route = "/"
            for mapping in method.get("mapping_annotations", []):
                if "Post" in mapping:
                    http_method = "POST"
                elif "Put" in mapping:
                    http_method = "PUT"
                elif "Delete" in mapping:
                    http_method = "DELETE"
                elif "Patch" in mapping:
                    http_method = "PATCH"
                route_match = re.search(r'"([^"]+)"', mapping)
                if route_match:
                    route = route_match.group(1)
            relevant_calls = ", ".join(service_calls[:3]) or "-"
            lines.append(
                f"| {ctrl['class_name']} | {method.get('name', '')} | {http_method} | {route} | {relevant_calls} |"
            )
    lines.append("")

    lines.append("## Service Dependencies")
    for svc in components.get("services", []):
        deps = svc.get("dependencies", svc.get("fields", []))
        dep_names = [
            f"`{dep.get('type', dep.get('name', ''))}`"
            for dep in deps
            if isinstance(dep, dict)
        ]
        lines.append(f"- **{svc['class_name']}** -> {', '.join(dep_names) or 'none'}")

    artifact_path = Path(artifacts_dir) / "04b-call-flow-graph.md"
    artifact_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return artifact_path


def discover_components_node(state: MigrationState) -> MigrationState:
    """Discover Spring Boot components, persist inventory, and generate contracts."""
    next_state = deepcopy(state)

    # ── Step 1: Discover components ──
    result = ComponentDiscoveryService().discover(
        input_dir=next_state["input_dir"],
        artifacts_dir=next_state["artifacts_dir"],
    )
    class_hierarchy_artifact = _generate_class_hierarchy_artifact(
        result.components,
        next_state["artifacts_dir"],
    )
    call_flow_artifact = _generate_call_flow_artifact(
        result.components,
        next_state["artifacts_dir"],
    )

    # Store component inventory in top-level state for validation
    next_state["component_inventory"] = result.components
    next_state["class_hierarchy"] = _build_class_hierarchy_dict(result.components)
    next_state["call_flow_graph"] = _build_call_flow_dict(result.components)

    # ── Step 2: Generate per-component business logic contracts ──
    contracts_dir = str(Path(next_state["artifacts_dir"]).parent / "contracts")
    try:
        contract_service = BusinessLogicContractService()
        manifest = contract_service.generate_contracts(
            input_dir=next_state["input_dir"],
            contracts_dir=contracts_dir,
            component_inventory=result.components,
        )
        next_state["contracts_dir"] = contracts_dir
        next_state["business_logic_contracts"] = manifest
        contracts_msg = f"Generated {len(manifest)} business logic contracts"
    except Exception as e:
        contracts_msg = f"Contract generation skipped: {e}"
        manifest = []

    # ── State updates ──
    next_state["status"] = "analyzing"
    next_state["current_step"] = "Discovered components & generated contracts"
    next_state["progress_pct"] = 45
    next_state["analysis_artifacts"] = {
        **next_state["analysis_artifacts"],
        "component_inventory": str(result.artifact_path),
        "class_hierarchy": str(class_hierarchy_artifact),
        "call_flow_graph": str(call_flow_artifact),
    }
    next_state["logs"] = [
        *next_state["logs"],
        f"Discovered {sum(len(v) for v in result.components.values())} Spring Boot components",
        contracts_msg,
    ]
    next_state["metadata"] = {
        **next_state["metadata"],
        "component_inventory": result.components,
        "class_hierarchy": next_state["class_hierarchy"],
        "call_flow_graph": next_state["call_flow_graph"],
    }
    return next_state
