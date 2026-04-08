"""Service converter agent — Java @Service → Python service class.

This is the MOST COMPLEX converter agent because services contain the bulk
of business logic. It reads docs context, existing models/schemas, and
performs an additional contract-compliance self-check.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.agents.converter_agents.base import BaseConverterAgent


PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


class ServiceConverterAgent(BaseConverterAgent):

    MAX_INNER_RETRIES = 3  # services get an extra retry

    def _get_component_type(self) -> str:
        return "service"

    def _get_output_path(self, component: dict[str, Any]) -> str:
        name = self._to_snake(str(component.get("class_name", "service")))
        return f"app/services/{name}.py"

    def _get_prompt_template_path(self) -> Path:
        return PROMPTS_DIR / "synthesize_service.md"

    def _build_llm_prompt(
        self,
        *,
        java_source: str,
        contract: str,
        existing_code: dict[str, str],
        discovered_technologies: list[str],
        docs_context: str,
        component: dict[str, Any],
    ) -> str:
        template_path = self._get_prompt_template_path()
        if template_path.exists():
            template = template_path.read_text(encoding="utf-8")
        else:
            template = (
                "Convert this Java @Service to Python.\n"
                "Preserve ALL business logic.\n\n"
                "### JAVA SOURCE\n{java_source}\n\n"
                "### CACHE CONTEXT\n{cache_context}\n\n"
                "### BUSINESS LOGIC CONTRACT\n{contract_md}\n\n"
                "### PYTHON DOCS CONTEXT\n{docs_context}\n\n"
                "### EXISTING MODELS\n{existing_models}\n\n"
                "### EXISTING SCHEMAS\n{existing_schemas}\n\n"
                "### TECHNOLOGIES\n{tech_text}\n"
            )

        cache_annotations = []
        for method in component.get("method_details") or []:
            for annotation in method.get("raw_annotations", []):
                if any(tag in annotation for tag in ("@Cacheable", "@CacheEvict", "@CachePut")):
                    cache_annotations.append(f"{method.get('name')}: {annotation}")
        cache_context = "\n".join(f"- {item}" for item in cache_annotations) or "- no cache annotations detected"

        return template.replace(
            "{java_source}", java_source
        ).replace(
            "{cache_context}", cache_context
        ).replace(
            "{contract_md}", contract
        ).replace(
            "{docs_context}", docs_context or "No documentation context."
        ).replace(
            "{existing_models}", existing_code.get("models", "# No models yet")
        ).replace(
            "{existing_schemas}", existing_code.get("schemas", "# No schemas yet")
        ).replace(
            "{existing_repos}", existing_code.get("repositories", "# No repos yet")
        ).replace(
            "{tech_text}", ", ".join(discovered_technologies) or "None"
        )


service_converter_agent = ServiceConverterAgent()
