"""Repository converter agent — Spring Data JPA Repository → SQLAlchemy repository."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.agents.converter_agents.base import BaseConverterAgent
from app.agents.tools.jpql_translator import JPQLTranslator


PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


class RepoConverterAgent(BaseConverterAgent):
    def __init__(self) -> None:
        super().__init__()
        self.jpql_translator = JPQLTranslator()

    def _get_component_type(self) -> str:
        return "repo"

    def _get_output_path(self, component: dict[str, Any]) -> str:
        name = self._to_snake(str(component.get("class_name", "repository")))
        return f"app/repositories/{name}.py"

    def _get_prompt_template_path(self) -> Path:
        return PROMPTS_DIR / "synthesize_repository.md"

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
                "Convert this Spring Data JPA Repository to SQLAlchemy 2.0.\n\n"
                "### JAVA SOURCE\n{java_source}\n\n"
                "### TRANSLATED QUERY HINTS\n{query_hints}\n\n"
                "### CONTRACT\n{contract_md}\n\n"
                "### EXISTING MODELS\n{existing_code}\n"
            )

        query_hints = self._build_query_hints(component)
        return template.replace(
            "{java_source}", java_source
        ).replace(
            "{query_hints}", query_hints
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
        base_code = super()._deterministic_convert(
            component=component,
            java_ir=java_ir,
            java_source=java_source,
        )
        if base_code:
            return base_code

        class_name = str(component.get("class_name", "Repository"))
        entity_name = class_name.removesuffix("Repository")
        method_details = component.get("method_details") or []
        translated_methods: list[tuple[str, str]] = []
        for method in method_details:
            method_name = str(method.get("name", ""))
            query_annotation = str(method.get("query") or "")
            translated = None
            if query_annotation:
                translated = self.jpql_translator.translate_jpql(query_annotation, entity_name)
            if not translated:
                translated = self.jpql_translator.translate_method_name(method_name, entity_name)
            if translated:
                translated_methods.append((method_name, translated))

        if not translated_methods:
            return None

        model_module = self._to_snake(entity_name)
        repo_name = f"{entity_name}Repository"
        lines = [
            f'"""Auto-generated repository for {entity_name}."""',
            "",
            "from __future__ import annotations",
            "",
            "from sqlalchemy import delete, exists, func, select",
            "from sqlalchemy.ext.asyncio import AsyncSession",
            f"from app.models.{model_module} import {entity_name}",
            "",
            "",
            f"class {repo_name}:",
            f"    def __init__(self, db: AsyncSession) -> None:",
            "        self.db = db",
            "",
        ]

        for method_name, translated in translated_methods:
            params = self._method_params(method_details, method_name)
            lines.append(f"    async def {self._to_snake(method_name)}(self{params}) -> object:")
            for body_line in translated.splitlines():
                lines.append(f"        {body_line}")
            lines.append("")

        return "\n".join(lines).strip() + "\n"

    def _build_query_hints(self, component: dict[str, Any]) -> str:
        entity_name = str(component.get("class_name", "Repository")).removesuffix("Repository")
        hints: list[str] = []
        for method in component.get("query_methods") or []:
            method_name = str(method.get("name", ""))
            query_annotation = str(method.get("query") or "")
            translated = None
            if query_annotation:
                translated = self.jpql_translator.translate_jpql(query_annotation, entity_name)
            if not translated:
                translated = self.jpql_translator.translate_method_name(method_name, entity_name)
            if translated:
                hints.append(f"- {method_name}:\n{translated}")
        return "\n".join(hints) or "- none"

    def _method_params(self, method_details: list[dict[str, Any]], method_name: str) -> str:
        for method in method_details:
            if method.get("name") != method_name:
                continue
            parameters = method.get("parameters") or []
            if not parameters:
                return ""
            rendered = []
            for parameter in parameters:
                param_name = self._to_snake(str(parameter.get("name", "value")))
                rendered.append(f"{param_name}: object")
            return ", " + ", ".join(rendered)
        return ""


repo_converter_agent = RepoConverterAgent()
