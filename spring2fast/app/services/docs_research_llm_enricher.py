"""LLM synthesis for dynamic documentation research."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from langchain_core.messages import HumanMessage

from app.core.llm import get_chat_model


class DocsResearchLLMEnricher:
    """Uses an LLM to select and summarize relevant docs candidates in batches."""

    def __init__(self, model=None) -> None:
        self.model = model or get_chat_model()

    @property
    def enabled(self) -> bool:
        return self.model is not None

    async def enrich_batch(self, *, candidates: list[dict[str, Any]]) -> list[dict[str, str]]:
        """Pick the best migration reference candidates (async, non-blocking)."""
        if not candidates:
            return []

        if not self.enabled:
            return [
                {
                    "java_technology": item["java_technology"],
                    "python_equivalent": item["static_reference"]["python_equivalent"] if item.get("static_reference") else item["java_technology"],
                    "official_docs": item["static_reference"]["official_docs"] if item.get("static_reference") else "",
                    "notes": item["static_reference"]["notes"] if item.get("static_reference") else "No dynamic enrichment applied.",
                }
                for item in candidates
            ]

        prompt = (
            "You are selecting the best Python migration references for Java backend technologies.\n"
            "Prefer official documentation and authoritative sources.\n"
            "Return strict JSON as an array of objects with keys: java_technology, python_equivalent, official_docs, notes.\n"
            "Do not invent URLs.\n\n"
            f"Candidates: {json.dumps(candidates, ensure_ascii=False)}\n"
        )

        try:
            response = await asyncio.wait_for(
                self.model.ainvoke([HumanMessage(content=prompt)]),
                timeout=60.0,
            )
        except (asyncio.TimeoutError, Exception):
            return [
                {
                    "java_technology": item["java_technology"],
                    "python_equivalent": (item.get("static_reference") or {}).get("python_equivalent", item["java_technology"]),
                    "official_docs": (item.get("static_reference") or {}).get("official_docs", ""),
                    "notes": (item.get("static_reference") or {}).get("notes", "LLM enrichment failed."),
                }
                for item in candidates
            ]

        content = response.content if isinstance(response.content, str) else "".join(
            part.get("text", "") for part in response.content if isinstance(part, dict)
        )
        return self._parse_response(content, candidates)

    def _parse_response(self, content: str, candidates: list[dict[str, Any]]) -> list[dict[str, str]]:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            cleaned = "\n".join(line for line in lines if not line.startswith("```")).strip()
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            parsed = []

        if not isinstance(parsed, list):
            parsed = []

        by_tech = {
            item.get("java_technology"): item
            for item in parsed
            if isinstance(item, dict) and item.get("java_technology")
        }

        results: list[dict[str, str]] = []
        for candidate in candidates:
            tech = candidate["java_technology"]
            static_reference = candidate.get("static_reference") or {}
            enriched = by_tech.get(tech, {})
            results.append(
                {
                    "java_technology": tech,
                    "python_equivalent": enriched.get("python_equivalent") or static_reference.get("python_equivalent") or tech,
                    "official_docs": enriched.get("official_docs") or static_reference.get("official_docs", ""),
                    "notes": enriched.get("notes") or static_reference.get("notes", "No dynamic enrichment applied."),
                }
            )
        return results
