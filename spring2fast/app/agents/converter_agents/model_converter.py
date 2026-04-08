"""Model converter agent — Java @Entity → SQLAlchemy 2.0 model."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.agents.converter_agents.base import BaseConverterAgent


PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


class ModelConverterAgent(BaseConverterAgent):

    def _get_component_type(self) -> str:
        return "model"

    def _get_output_path(self, component: dict[str, Any]) -> str:
        name = self._to_snake(str(component.get("class_name", "model")))
        return f"app/models/{name}.py"

    def _get_prompt_template_path(self) -> Path:
        return PROMPTS_DIR / "synthesize_model.md"

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
                "Convert this Java @Entity to a SQLAlchemy 2.0 model.\n"
                "Use Mapped[T] and mapped_column() syntax.\n\n"
                "### JAVA SOURCE\n{java_source}\n\n"
                "### INHERITED FIELDS\n{inherited_fields}\n\n"
                "### CONTRACT\n{contract_md}\n\n"
                "### EXISTING MODELS\n{existing_code}\n"
            )

        inherited_fields = component.get("inherited_fields") or []
        inherited_text = "\n".join(
            f"- {field['name']}: {field['type']}"
            for field in inherited_fields
        ) or "- none"

        return template.replace(
            "{java_source}", java_source
        ).replace(
            "{inherited_fields}", inherited_text
        ).replace(
            "{contract_md}", contract
        ).replace(
            "{existing_code}", existing_code.get("models", "# No existing models")
        )


model_converter_agent = ModelConverterAgent()
