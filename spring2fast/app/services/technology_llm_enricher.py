"""Optional LLM enrichment for technology discovery."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import HumanMessage

from app.core.llm import get_chat_model


class TechnologyLLMEnricher:
    """Uses an LLM to enrich deterministic technology discovery output."""

    def __init__(self, model=None) -> None:
        self.model = model or get_chat_model()

    @property
    def enabled(self) -> bool:
        return self.model is not None

    def enrich(
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

        prompt = (
            "You are analyzing a Java backend migration candidate.\n"
            "Given the deterministic scan output and file snapshot, infer additional likely technologies.\n"
            "Return strict JSON with keys: summary, additional_technologies, notes.\n"
            "Rules:\n"
            "- additional_technologies must be a JSON array of short lowercase strings.\n"
            "- notes must be a JSON array of short strings.\n"
            "- Do not repeat technologies already detected.\n"
            "- Be conservative and only infer technologies supported by the evidence.\n\n"
            f"Detected technologies: {detected_technologies}\n"
            f"Build files: {build_files}\n"
            f"Java file count: {java_file_count}\n"
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
            return {"summary": cleaned[:500] or None, "additional_technologies": [], "notes": []}

        return {
            "summary": parsed.get("summary"),
            "additional_technologies": parsed.get("additional_technologies", []),
            "notes": parsed.get("notes", []),
        }
