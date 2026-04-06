"""Optional LLM enrichment for business logic extraction."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import HumanMessage

from app.core.llm import get_chat_model


class BusinessLogicLLMEnricher:
    """Uses an LLM to summarize extracted business behavior."""

    def __init__(self, model=None) -> None:
        self.model = model or get_chat_model()

    @property
    def enabled(self) -> bool:
        return self.model is not None

    def enrich(self, *, file_snapshot: str, extracted_rules: list[str]) -> dict[str, Any]:
        """Return an optional business-logic summary."""
        if not self.enabled:
            return {"summary": None, "additional_rules": []}

        prompt = (
            "You are analyzing Java backend business logic for migration to FastAPI.\n"
            "Given deterministic extracted rules and file snippets, summarize the key business behavior.\n"
            "Return strict JSON with keys: summary, additional_rules.\n"
            "Rules:\n"
            "- summary should be a concise paragraph.\n"
            "- additional_rules must be an array of short bullet-like strings.\n"
            "- Only include behavior strongly supported by the file snapshot.\n\n"
            f"Extracted rules: {extracted_rules}\n"
            "File snapshot:\n"
            f"{file_snapshot}\n"
        )

        response = self.model.invoke([HumanMessage(content=prompt)])
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
