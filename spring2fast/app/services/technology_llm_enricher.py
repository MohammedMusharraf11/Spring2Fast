"""LLM enrichment for technology discovery — uses dedicated system prompt."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.prompt_loader import load_system_prompt
from app.core.llm import get_analysis_model


class TechnologyLLMEnricher:
    """Uses an LLM to enrich deterministic technology discovery output."""

    def __init__(self, model=None) -> None:
        self.model = model or get_analysis_model()
        self._system_prompt = load_system_prompt("system_tech_discovery")

    @property
    def enabled(self) -> bool:
        return self.model is not None

    async def enrich(
        self,
        *,
        file_snapshot: str,
        detected_technologies: list[str],
        build_files: list[str],
        java_file_count: int,
    ) -> dict[str, Any]:
        """Return LLM-enriched technology observations."""
        if not self.enabled:
            return {"summary": None, "additional_technologies": [], "notes": []}

        user_prompt = (
            f"Detected technologies: {detected_technologies}\n"
            f"Build files: {build_files}\n"
            f"Java file count: {java_file_count}\n"
            f"File snapshot:\n{file_snapshot}\n"
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
            return {"summary": None, "additional_technologies": [], "notes": []}

        content = response.content if isinstance(response.content, str) else "".join(
            part.get("text", "") for part in response.content if isinstance(part, dict)
        )
        return self._parse_json_response(content)

    def _parse_json_response(self, content: str) -> dict[str, Any]:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            cleaned = "\n".join(line for line in lines if not line.startswith("```")).strip()
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            return {"summary": cleaned[:500] or None, "additional_technologies": [], "notes": []}

        return {
            "summary": parsed.get("summary"),
            "additional_technologies": parsed.get("additional_technologies", []),
            "notes": parsed.get("notes", []),
        }
