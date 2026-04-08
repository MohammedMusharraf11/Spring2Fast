"""Controller converter agent — Java @RestController → FastAPI APIRouter."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.agents.converter_agents.base import BaseConverterAgent


PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


class ControllerConverterAgent(BaseConverterAgent):

    def _get_component_type(self) -> str:
        return "controller"

    def _get_output_path(self, component: dict[str, Any]) -> str:
        name = self._to_snake(str(component.get("class_name", "controller")))
        return f"app/api/v1/endpoints/{name}.py"

    def _get_prompt_template_path(self) -> Path:
        return PROMPTS_DIR / "synthesize_controller.md"

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
                "Convert this Java Spring controller to a FastAPI APIRouter.\n"
                "If it is an MVC controller that returns views, redesign it as a REST API that returns the underlying data as JSON instead of rendering templates.\n\n"
                "### JAVA SOURCE\n{java_source}\n\n"
                "### CONTRACT\n{contract_md}\n\n"
                "### EXISTING SERVICES\n{existing_services}\n\n"
                "### EXISTING SCHEMAS\n{existing_schemas}\n"
            )

        # Build security context
        has_security = (
            "spring-security" in discovered_technologies
            or "jwt" in discovered_technologies
        )
        security_ctx = ""
        if has_security:
            security_ctx = (
                "YES — Spring Security / JWT detected.\n"
                "Import `from app.core.security import get_current_user`\n"
                "Add `current_user: str = Depends(get_current_user)` to protected endpoints."
            )
        else:
            security_ctx = "No security detected. All endpoints are public."

        return template.replace(
            "{java_source}", java_source
        ).replace(
            "{contract_md}", contract
        ).replace(
            "{existing_services}", existing_code.get("services", "# No services yet")
        ).replace(
            "{existing_schemas}", existing_code.get("schemas", "# No schemas yet")
        ).replace(
            "{security_context}", security_ctx
        )


controller_converter_agent = ControllerConverterAgent()
