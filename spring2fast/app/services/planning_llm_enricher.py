"""LLM enrichment for migration planning — uses dedicated system prompt."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.prompt_loader import load_system_prompt
from app.core.llm import get_planning_model


class PlanningLLMEnricher:
    """Uses an LLM to refine migration steps and risks."""

    def __init__(self, model=None) -> None:
        self.model = model or get_planning_model()
        self._system_prompt = load_system_prompt("system_migration_planning")

    @property
    def enabled(self) -> bool:
        return self.model is not None

    async def enrich(
        self,
        *,
        discovered_technologies: list[str],
        business_rules: list[str],
        docs_references: list[dict[str, str]],
        target_files: list[str],
        component_inventory: dict[str, Any] | None = None,
        class_hierarchy: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return plan refinements from the LLM."""
        empty = {"implementation_steps": [], "risk_items": [], "target_files": [], "per_component_notes": {}}
        if not self.enabled:
            return empty

        user_prompt = (
            f"Discovered technologies: {discovered_technologies}\n"
            f"Business rules: {business_rules[:20]}\n"
            f"Component inventory summary: {_summarize_inventory(component_inventory)}\n"
            f"Class hierarchy: {class_hierarchy}\n"
            f"Docs references: {docs_references[:10]}\n"
            f"Current target files: {target_files}\n"
        )

        try:
            response = await asyncio.wait_for(
                self.model.ainvoke([
                    SystemMessage(content=self._system_prompt),
                    HumanMessage(content=user_prompt),
                ]),
                timeout=60.0,
            )
        except (asyncio.TimeoutError, Exception):
            return empty

        content = response.content if isinstance(response.content, str) else "".join(
            part.get("text", "") for part in response.content if isinstance(part, dict)
        )
        return self._parse_response(content)

    def _parse_response(self, content: str) -> dict[str, Any]:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            cleaned = "\n".join(line for line in lines if not line.startswith("```")).strip()
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            return {"implementation_steps": [], "risk_items": [], "target_files": [], "per_component_notes": {}}
        return {
            "implementation_steps": [item for item in parsed.get("implementation_steps", []) if isinstance(item, str)],
            "risk_items": [item for item in parsed.get("risk_items", []) if isinstance(item, str)],
            "target_files": [item for item in parsed.get("target_files", []) if isinstance(item, str)],
            "per_component_notes": {
                str(key): str(value)
                for key, value in (parsed.get("per_component_notes", {}) or {}).items()
                if isinstance(key, str) and isinstance(value, str)
            },
        }


def _summarize_inventory(component_inventory: dict[str, Any] | None) -> dict[str, int]:
    if not component_inventory:
        return {}
    return {
        str(category): len(items) if isinstance(items, list) else 0
        for category, items in component_inventory.items()
    }
