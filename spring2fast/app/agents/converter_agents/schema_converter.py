"""Schema converter agent — Java DTO/Request/Response → Pydantic v2 schema."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.agents.converter_agents.base import BaseConverterAgent
from app.agents.tools.converter_tools import parse_bean_validation


PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


class SchemaConverterAgent(BaseConverterAgent):

    def _get_component_type(self) -> str:
        return "schema"

    def _get_output_path(self, component: dict[str, Any]) -> str:
        name = self._to_snake(str(component.get("class_name", "schema")))
        return f"app/schemas/{name}.py"

    def _get_prompt_template_path(self) -> Path:
        return PROMPTS_DIR / "synthesize_schema.md"

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
                "Convert this Java DTO to a Pydantic v2 BaseModel.\n\n"
                "### JAVA SOURCE\n{java_source}\n\n"
                "### FIELD VALIDATION CONSTRAINTS\n{validation_context}\n\n"
                "### CONTRACT\n{contract_md}\n\n"
                "### EXISTING MODELS\n{existing_code}\n"
            )

        validation_context = parse_bean_validation(component.get("all_fields") or component.get("fields") or [])
        validation_text = "\n".join(
            f"- {field_name}: {rules}"
            for field_name, rules in validation_context.items()
        ) or "- none"

        return template.replace(
            "{java_source}", java_source
        ).replace(
            "{validation_context}", validation_text
        ).replace(
            "{contract_md}", contract
        ).replace(
            "{existing_code}", existing_code.get("models", "# No existing models")
        )


schema_converter_agent = SchemaConverterAgent()
