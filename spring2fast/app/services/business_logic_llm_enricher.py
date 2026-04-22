"""LLM enrichment for business logic extraction — uses dedicated system prompt."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.prompt_loader import load_system_prompt
from app.core.llm import get_analysis_model


class BusinessLogicLLMEnricher:
    """Uses an LLM to summarize extracted business behavior."""

    def __init__(self, model=None) -> None:
        self.model = model or get_analysis_model()
        self._system_prompt = load_system_prompt("system_business_logic")

    @property
    def enabled(self) -> bool:
        return self.model is not None

    async def enrich(self, *, file_snapshot: str, extracted_rules: list[str]) -> dict[str, Any]:
        """Return an optional business-logic summary."""
        if not self.enabled:
            return {"summary": None, "additional_rules": []}

        user_prompt = (
            f"Extracted rules: {extracted_rules}\n"
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
            return {"summary": None, "additional_rules": []}

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
            return {"summary": cleaned[:700] or None, "additional_rules": []}

        return {
            "summary": parsed.get("summary"),
            "additional_rules": parsed.get("additional_rules", []),
        }
