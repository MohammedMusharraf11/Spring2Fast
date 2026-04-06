"""Exception handler converter — @ControllerAdvice → FastAPI exception handlers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.agents.converter_agents.base import BaseConverterAgent


PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


class ExceptionConverterAgent(BaseConverterAgent):

    def _get_component_type(self) -> str:
        return "exception_handler"

    def _get_output_path(self, component: dict[str, Any]) -> str:
        name = self._to_snake(str(component.get("class_name", "exceptions")))
        return f"app/core/{name}.py"

    def _get_prompt_template_path(self) -> Path:
        return PROMPTS_DIR / "synthesize_exception_handler.md"

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
                "Convert this Java @ControllerAdvice to FastAPI exception handlers.\n\n"
                "### JAVA SOURCE\n{java_source}\n\n"
                "### CONTRACT\n{contract_md}\n"
            )

        return template.replace(
            "{java_source}", java_source
        ).replace(
            "{contract_md}", contract
        )


exception_converter_agent = ExceptionConverterAgent()
