"""Component discovery node — discovers Spring components and generates contracts."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from app.agents.state import MigrationState
from app.services.component_discovery_service import ComponentDiscoveryService
from app.services.business_logic_contract_service import BusinessLogicContractService


def discover_components_node(state: MigrationState) -> MigrationState:
    """Discover Spring Boot components, persist inventory, and generate contracts."""
    next_state = deepcopy(state)

    # ── Step 1: Discover components ──
    result = ComponentDiscoveryService().discover(
        input_dir=next_state["input_dir"],
        artifacts_dir=next_state["artifacts_dir"],
    )

    # Store component inventory in top-level state for validation
    next_state["component_inventory"] = result.components

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
    }
    next_state["logs"] = [
        *next_state["logs"],
        f"Discovered {sum(len(v) for v in result.components.values())} Spring Boot components",
        contracts_msg,
    ]
    next_state["metadata"] = {
        **next_state["metadata"],
        "component_inventory": result.components,
    }
    return next_state
