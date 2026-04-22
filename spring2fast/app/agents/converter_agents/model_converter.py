"""Model converter agent — Java @Entity → SQLAlchemy 2.0 model."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.agents.converter_agents.base import BaseConverterAgent
from app.agents.tools import converter_tools as tools


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

        table_name = str(component.get("table_name") or "").strip()
        inheritance = str(component.get("inheritance_strategy") or "").strip()
        extends = str(component.get("extends") or "").strip()
        table_hint = ""
        if table_name:
            table_hint += f"\nEXPLICIT TABLE NAME: {table_name} (use this exactly in __tablename__)"
        if extends:
            table_hint += (
                f"\nINHERITANCE: This class extends {extends}. "
                "You MUST include all inherited fields, especially the primary key `id`."
            )
        if inheritance:
            table_hint += f"\nJPA STRATEGY: {inheritance}"
        if not table_hint:
            table_hint = "\nNo explicit table or inheritance hints."

        return template.replace(
            "{java_source}", java_source
        ).replace(
            "{table_hint}", table_hint
        ).replace(
            "{inherited_fields}", inherited_text
        ).replace(
            "{contract_md}", contract
        ).replace(
            "{existing_code}", existing_code.get("models", "# No existing models")
        )

    def _deterministic_convert(
        self,
        *,
        component: dict[str, Any],
        java_ir: dict[str, Any],
        java_source: str,
    ) -> str | None:
        classes = java_ir.get("classes", [])
        if not classes:
            return None

        cls = classes[0]
        raw_annotations = cls.get("annotations", [])
        annotations = [
            a.get("name", "") if isinstance(a, dict) else str(a)
            for a in raw_annotations
        ]
        if "Entity" not in annotations and "@Entity" not in annotations:
            return None

        cls["all_fields"] = component.get("all_fields") or cls.get("fields", [])
        cls["table_name"] = component.get("table_name")
        cls["inheritance_strategy"] = component.get("inheritance_strategy")
        return tools.deterministic_convert("model", java_ir)


model_converter_agent = ModelConverterAgent()
