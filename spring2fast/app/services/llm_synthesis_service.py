"""LLM-driven code synthesis with per-layer prompts and inter-layer context.

This is the core engine that translates Java source into Python using
specialized prompt templates, existing generated code for context,
and a self-correction loop for syntax errors.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.llm import get_code_model


PROMPT_DIR = Path(__file__).parent.parent / "agents" / "prompts"

# Map chunk keys to prompt template filenames
_PROMPT_MAP = {
    "models": "synthesize_model.md",
    "schemas": "synthesize_schema.md",
    "services": "synthesize_service.md",
    "controllers": "synthesize_controller.md",
    "repositories": "synthesize_repository.md",
}


class LLMSynthesisService:
    """Service for synthesizing Python code from Java source using LLMs."""

    MAX_RETRIES = 2

    def __init__(self) -> None:
        self.llm = get_code_model()

    async def synthesize_module(
        self,
        *,
        module_type: str,
        java_source: str,
        docs_context: str = "",
        business_rules: list[str] | None = None,
        discovered_tech: list[str] | None = None,
        contract_md: str = "",
        existing_code: dict[str, str] | None = None,
    ) -> str:
        """Synthesize a complete Python module from Java source.

        Parameters
        ----------
        module_type:
            The layer being generated (models, schemas, services, controllers, repositories).
        java_source:
            Raw Java source code to translate.
        docs_context:
            Python library documentation snippets for 3rd-party integrations.
        business_rules:
            Extracted business rules list (legacy compat).
        discovered_tech:
            List of detected technologies.
        contract_md:
            Structured `.md` contract for this specific component.
        existing_code:
            Dict of ``{layer_name: concatenated_generated_code}`` for context.
        """
        if not self.llm:
            return "# LLM not configured for synthesis. Falling back to template.\n"

        business_rules = business_rules or []
        discovered_tech = discovered_tech or []
        existing_code = existing_code or {}

        # Build the prompt from the specialized template
        prompt_text = self._build_prompt(
            module_type=module_type,
            java_source=java_source,
            docs_context=docs_context,
            business_rules=business_rules,
            discovered_tech=discovered_tech,
            contract_md=contract_md,
            existing_code=existing_code,
        )

        # Generate code
        content = await self._invoke_llm(prompt_text)

        # Validate and self-correct
        content = await self._validate_and_fix(content, prompt_text)

        return content

    def _build_prompt(
        self,
        *,
        module_type: str,
        java_source: str,
        docs_context: str,
        business_rules: list[str],
        discovered_tech: list[str],
        contract_md: str,
        existing_code: dict[str, str],
    ) -> str:
        """Build the full prompt by loading the template and injecting variables."""

        # Load the specialized template
        template_name = _PROMPT_MAP.get(module_type, "synthesize_service.md")
        template_path = PROMPT_DIR / template_name

        if template_path.exists():
            template = template_path.read_text(encoding="utf-8")
        else:
            # Fallback generic prompt
            template = self._generic_prompt()

        # Build context strings
        rules_text = "\n".join(f"- {r}" for r in business_rules) if business_rules else "No rules extracted."
        tech_text = ", ".join(discovered_tech) if discovered_tech else "None detected."

        # Build existing code context for inter-layer references
        existing_models = existing_code.get("models", "# No models generated yet")
        existing_schemas = existing_code.get("schemas", "# No schemas generated yet")
        existing_services = existing_code.get("services", "# No services generated yet")

        # Substitute all template variables
        prompt = template
        substitutions = {
            "{java_source}": java_source or "# No Java source available",
            "{contract_md}": contract_md or "No contract provided.",
            "{docs_context}": docs_context or "No documentation context available.",
            "{rules_text}": rules_text,
            "{tech_text}": tech_text,
            "{existing_code}": existing_models,
            "{existing_models}": existing_models,
            "{existing_schemas}": existing_schemas,
            "{existing_services}": existing_services,
        }
        for key, value in substitutions.items():
            prompt = prompt.replace(key, value)

        return prompt

    async def _invoke_llm(self, prompt: str) -> str:
        """Invoke the LLM and clean the response."""
        try:
            response = await self.llm.ainvoke([
                SystemMessage(content=(
                    "You are an expert software architect specializing in migrating "
                    "Java Spring Boot systems to Python FastAPI backends. "
                    "Output ONLY valid Python code. No markdown fences, no explanations."
                )),
                HumanMessage(content=prompt),
            ])
            content = response.content if isinstance(response.content, str) else str(response.content)
            return self._strip_markdown_fences(content)
        except Exception as e:
            return f"# Error during LLM synthesis: {e!s}\n# Falling back to template logic.\n"

    async def _validate_and_fix(self, code: str, original_prompt: str) -> str:
        """Validate generated Python code and self-correct syntax errors."""
        for attempt in range(self.MAX_RETRIES):
            try:
                ast.parse(code)
                return code  # Valid Python!
            except SyntaxError as e:
                if attempt < self.MAX_RETRIES - 1 and self.llm:
                    code = await self._retry_with_error(code, str(e))
                else:
                    # Add the error as a comment and return best effort
                    return f"# WARNING: Syntax error detected but could not auto-fix: {e}\n{code}"
        return code

    async def _retry_with_error(self, broken_code: str, error: str) -> str:
        """Ask the LLM to fix a syntax error in generated code."""
        fix_prompt = (
            "The following Python code has a syntax error. Fix it and return ONLY "
            "the corrected Python code. No markdown, no explanations.\n\n"
            f"ERROR: {error}\n\n"
            f"CODE:\n{broken_code}"
        )
        try:
            response = await self.llm.ainvoke([
                SystemMessage(content="You are a Python code fixer. Return ONLY valid Python code."),
                HumanMessage(content=fix_prompt),
            ])
            content = response.content if isinstance(response.content, str) else str(response.content)
            return self._strip_markdown_fences(content)
        except Exception:
            return broken_code

    @staticmethod
    def _strip_markdown_fences(content: str) -> str:
        """Remove markdown code fences from LLM output."""
        content = content.strip()
        # Remove ```python ... ``` or ``` ... ```
        if content.startswith("```python"):
            content = content[len("```python"):]
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        return content.strip()

    @staticmethod
    def _generic_prompt() -> str:
        """Fallback prompt when no template file exists."""
        return (
            "You are migrating a Java Spring Boot component to Python FastAPI.\n\n"
            "RULES:\n"
            "1. Output ONLY valid Python code.\n"
            "2. Use FastAPI, SQLAlchemy 2.0+, and Pydantic 2.0+.\n"
            "3. Preserve all business logic, validation, and error handling.\n"
            "4. Use proper type hints.\n\n"
            "### JAVA SOURCE\n{java_source}\n\n"
            "### BUSINESS LOGIC CONTRACT\n{contract_md}\n\n"
            "### DOCUMENTATION CONTEXT\n{docs_context}\n"
        )
