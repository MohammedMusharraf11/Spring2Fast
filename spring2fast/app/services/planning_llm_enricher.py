"""Optional LLM enrichment for migration planning."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from langchain_core.messages import HumanMessage

from app.core.llm import get_chat_model


class PlanningLLMEnricher:
    """Uses an LLM to refine migration steps and risks."""

    def __init__(self, model=None) -> None:
        self.model = model or get_chat_model()

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
    ) -> dict[str, Any]:
        """Return plan refinements from the LLM (async, non-blocking)."""
        if not self.enabled:
            return {"implementation_steps": [], "risk_items": [], "target_files": []}

        prompt = (
            "You are refining a migration plan from Spring Boot to FastAPI.\n"
            "Return strict JSON with keys: implementation_steps, risk_items, target_files.\n"
            "Only suggest backend-related items. Exclude frontend/template migration.\n\n"
            f"Discovered technologies: {discovered_technologies}\n"
            f"Business rules: {business_rules[:20]}\n"
            f"Docs references: {docs_references[:10]}\n"
            f"Current target files: {target_files}\n"
        )

        try:
            response = await asyncio.wait_for(
                self.model.ainvoke([HumanMessage(content=prompt)]),
                timeout=60.0,
            )
        except asyncio.TimeoutError:
            return {"implementation_steps": [], "risk_items": [], "target_files": []}
        except Exception:
            return {"implementation_steps": [], "risk_items": [], "target_files": []}

        content = response.content if isinstance(response.content, str) else "".join(
            part.get("text", "") for part in response.content if isinstance(part, dict)
        )
        return self._parse_response(content)

    def _parse_response(self, content: str) -> dict[str, list[str]]:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            cleaned = "\n".join(line for line in lines if not line.startswith("```")).strip()
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            return {"implementation_steps": [], "risk_items": [], "target_files": []}
        return {
            "implementation_steps": [item for item in parsed.get("implementation_steps", []) if isinstance(item, str)],
            "risk_items": [item for item in parsed.get("risk_items", []) if isinstance(item, str)],
            "target_files": [item for item in parsed.get("target_files", []) if isinstance(item, str)],
        }
