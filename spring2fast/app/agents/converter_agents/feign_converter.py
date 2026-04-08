"""Feign client converter agent."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.agents.converter_agents.base import BaseConverterAgent


PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


class FeignConverterAgent(BaseConverterAgent):
    def _get_component_type(self) -> str:
        return "feign_client"

    def _get_output_path(self, component: dict[str, Any]) -> str:
        return f"app/clients/{self._to_snake(str(component.get('class_name', 'client')))}.py"

    def _get_prompt_template_path(self) -> Path:
        return PROMPTS_DIR / "synthesize_feign_client.md"

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
                "Convert this Feign client to an async httpx client.\n\n"
                "### JAVA SOURCE\n{java_source}\n\n"
                "### CONTRACT\n{contract_md}\n\n"
                "### EXISTING CLIENTS\n{existing_code}\n\n"
                "### DOCS CONTEXT\n{docs_context}\n\n"
                "### DETECTED TECHNOLOGIES\n{tech_text}\n"
            )

        return template.replace(
            "{java_source}", java_source
        ).replace(
            "{contract_md}", contract
        ).replace(
            "{existing_code}", existing_code.get("clients", "# No existing clients")
        ).replace(
            "{docs_context}", docs_context or "No documentation context."
        ).replace(
            "{tech_text}", ", ".join(discovered_technologies) or "None"
        )

    def _deterministic_convert(
        self,
        *,
        component: dict[str, Any],
        java_ir: dict[str, Any],
        java_source: str,
    ) -> str | None:
        class_name = str(component.get("class_name", "ServiceClient"))
        config_key = self._extract_config_key(java_source, class_name)
        methods = component.get("method_details") or []
        lines = [
            f'"""HTTP client migrated from {class_name}."""',
            "",
            "from __future__ import annotations",
            "",
            "import httpx",
            "from app.core.config import settings",
            "",
            "",
            f"class {class_name}:",
            "    def __init__(self) -> None:",
            f"        self.base_url = settings.{config_key}",
            "        self.timeout = 30.0",
            "",
        ]

        for method in methods:
            method_name = self._to_snake(str(method.get("name", "call_remote")))
            http_method, path = self._extract_http_mapping(method.get("raw_annotations") or [])
            params = method.get("parameters") or []
            signature = ", ".join(
                f"{self._to_snake(str(param.get('name', 'value')))}: object"
                for param in params
            )
            if signature:
                signature = ", " + signature
            path_expr = self._path_expression(path, params)
            body_param = next(
                (self._to_snake(str(param.get("name", "body"))) for param in params if "@RequestBody" in " ".join(param.get("annotations", []))),
                None,
            )
            lines.extend(
                [
                    f"    async def {method_name}(self{signature}) -> dict:",
                    "        async with httpx.AsyncClient(timeout=self.timeout) as client:",
                    f"            response = await client.{http_method}(f\"{{self.base_url}}{path_expr}\"{', json=' + body_param if body_param else ''})",
                    "            response.raise_for_status()",
                    "            return response.json()",
                    "",
                ]
            )
        return "\n".join(lines).strip() + "\n"

    def _extract_config_key(self, java_source: str, class_name: str) -> str:
        match = re.search(r'@FeignClient\s*\((.*?)\)', java_source, re.DOTALL)
        if match:
            args = match.group(1)
            url_match = re.search(r'url\s*=\s*"\$\{([^}]+)\}"', args)
            if url_match:
                return url_match.group(1).replace(".", "_").replace("-", "_")
            name_match = re.search(r'name\s*=\s*"([^"]+)"', args)
            if name_match:
                return f"{name_match.group(1).replace('-', '_')}_url"
        return f"{self._to_snake(class_name.removesuffix('Client'))}_url"

    def _extract_http_mapping(self, annotations: list[str]) -> tuple[str, str]:
        for annotation in annotations:
            if "@GetMapping" in annotation:
                return "get", self._extract_path(annotation)
            if "@PostMapping" in annotation:
                return "post", self._extract_path(annotation)
            if "@PutMapping" in annotation:
                return "put", self._extract_path(annotation)
            if "@DeleteMapping" in annotation:
                return "delete", self._extract_path(annotation)
        return "get", "/"

    def _extract_path(self, annotation: str) -> str:
        match = re.search(r'"([^"]+)"', annotation)
        return match.group(1) if match else "/"

    def _path_expression(self, path: str, params: list[dict[str, Any]]) -> str:
        expr = path
        for param in params:
            name = self._to_snake(str(param.get("name", "value")))
            expr = expr.replace("{" + str(param.get("name", "")) + "}", "{" + name + "}")
        return expr


feign_converter_agent = FeignConverterAgent()
