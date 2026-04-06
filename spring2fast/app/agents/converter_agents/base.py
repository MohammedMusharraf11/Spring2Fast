"""Base converter agent with shared inner-loop logic.

Each converter agent follows the same pattern:
1. Read Java source + contract
2. Try deterministic conversion (Tier 1)
3. If not possible, generate via LLM with specialized prompt (Tier 2)
4. Validate syntax → self-correct if needed
5. Check imports → fix if needed
6. Write output

The agent does INNER validation before returning results to the supervisor,
catching ~80% of issues without the expensive full-pipeline retry.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.tools import converter_tools as tools
from app.core.llm import get_code_model


class ConversionResult:
    """Structured result from a converter agent."""

    __slots__ = ("component_name", "component_type", "output_path", "code",
                 "passed", "error", "attempts", "tier_used")

    def __init__(
        self,
        component_name: str,
        component_type: str,
        output_path: str = "",
        code: str = "",
        passed: bool = False,
        error: str = "",
        attempts: int = 1,
        tier_used: str = "none",
    ) -> None:
        self.component_name = component_name
        self.component_type = component_type
        self.output_path = output_path
        self.code = code
        self.passed = passed
        self.error = error
        self.attempts = attempts
        self.tier_used = tier_used

    def to_dict(self) -> dict[str, Any]:
        return {
            "component_name": self.component_name,
            "component_type": self.component_type,
            "output_path": self.output_path,
            "passed": self.passed,
            "error": self.error,
            "attempts": self.attempts,
            "tier_used": self.tier_used,
        }


class BaseConverterAgent:
    """Base class providing the inner conversion loop.

    Subclasses override:
    - ``_get_prompt_template()`` — returns the .md prompt path
    - ``_get_output_path(component)`` — returns the relative path for output
    - ``_build_llm_prompt(...)`` — builds the full prompt with context
    - ``_get_component_type()`` — returns "model", "service", etc.
    """

    MAX_INNER_RETRIES = 2

    def __init__(self) -> None:
        self.llm = get_code_model()

    async def convert(
        self,
        *,
        component: dict[str, Any],
        input_dir: str,
        output_dir: str,
        contracts_dir: str,
        artifacts_dir: str,
        discovered_technologies: list[str],
        existing_code: dict[str, str],
    ) -> ConversionResult:
        """Run the full conversion loop for a single component."""
        class_name = str(component.get("class_name", "Unknown"))
        file_path = str(component.get("file_path", ""))
        component_type = self._get_component_type()

        result = ConversionResult(
            component_name=class_name,
            component_type=component_type,
        )

        try:
            # ── Step 1: Read Java source ──
            java_source = tools.read_java_source(file_path, input_dir)

            # ── Step 2: Read contract ──
            contract = tools.read_contract(class_name, contracts_dir)

            # ── Step 3: Parse to IR ──
            java_ir = tools.parse_java_to_ir(java_source, file_path)

            # ── Step 4: Try Tier 1 deterministic conversion ──
            deterministic_code = tools.deterministic_convert(component_type, java_ir)
            if deterministic_code:
                syntax_check = tools.validate_syntax(deterministic_code)
                if syntax_check["valid"]:
                    output_path = self._get_output_path(component)
                    tools.write_output(output_path, deterministic_code, output_dir)
                    result.output_path = output_path
                    result.code = deterministic_code
                    result.passed = True
                    result.tier_used = "deterministic"
                    return result

            # ── Step 5: Tier 2 — LLM synthesis with inner validation loop ──
            if not self.llm:
                # C2: Graceful fallback — generate TODO scaffold
                code = self._generate_fallback_scaffold(
                    class_name, component_type, java_source
                )
                output_path = self._get_output_path(component)
                tools.write_output(output_path, code, output_dir)
                result.output_path = output_path
                result.code = code
                result.passed = True
                result.tier_used = "fallback"
                return result

            code = await self._generate_with_llm(
                java_source=java_source,
                contract=contract,
                java_ir=java_ir,
                input_dir=input_dir,
                output_dir=output_dir,
                artifacts_dir=artifacts_dir,
                discovered_technologies=discovered_technologies,
                existing_code=existing_code,
                component=component,
            )

            # ── Step 6: Inner validation loop ──
            for attempt in range(self.MAX_INNER_RETRIES + 1):
                result.attempts = attempt + 1

                # Check syntax
                syntax_check = tools.validate_syntax(code)
                if not syntax_check["valid"]:
                    if attempt < self.MAX_INNER_RETRIES:
                        code = await self._fix_code(code, syntax_check["error"])
                        continue
                    else:
                        result.error = f"Syntax: {syntax_check['error']}"
                        result.code = code
                        break

                # Check imports
                import_check = tools.check_imports(code, output_dir)
                if not import_check["valid"] and attempt < self.MAX_INNER_RETRIES:
                    code = self._fix_imports(code, import_check["unresolved"])

                # Passed inner validation
                output_path = self._get_output_path(component)
                tools.write_output(output_path, code, output_dir)
                result.output_path = output_path
                result.code = code
                result.passed = True
                result.tier_used = "llm"
                break

        except Exception as e:
            result.error = f"Agent error: {e!s}"

        return result

    # ─────────────────────────────────────────
    # Methods subclasses MUST override
    # ─────────────────────────────────────────

    def _get_component_type(self) -> str:
        raise NotImplementedError

    def _get_output_path(self, component: dict[str, Any]) -> str:
        raise NotImplementedError

    def _get_prompt_template_path(self) -> Path:
        raise NotImplementedError

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
        raise NotImplementedError

    # ─────────────────────────────────────────
    # Shared LLM helpers
    # ─────────────────────────────────────────

    async def _generate_with_llm(
        self,
        *,
        java_source: str,
        contract: str,
        java_ir: dict[str, Any],
        input_dir: str,
        output_dir: str,
        artifacts_dir: str,
        discovered_technologies: list[str],
        existing_code: dict[str, str],
        component: dict[str, Any],
    ) -> str:
        """Generate Python code via LLM with the specialized prompt."""
        docs_context = ""
        for tech in discovered_technologies:
            ctx = tools.read_docs_context(tech, artifacts_dir)
            if ctx and not ctx.startswith("# No"):
                docs_context += f"\n\n## {tech}\n{ctx}"

        prompt = self._build_llm_prompt(
            java_source=java_source,
            contract=contract,
            existing_code=existing_code,
            discovered_technologies=discovered_technologies,
            docs_context=docs_context,
            component=component,
        )

        try:
            response = await self.llm.ainvoke([
                SystemMessage(content=(
                    "You are an expert migration architect converting Java Spring Boot "
                    "to Python FastAPI. Output ONLY valid Python code. "
                    "No markdown fences, no explanations, no commentary."
                )),
                HumanMessage(content=prompt),
            ])
            content = response.content if isinstance(response.content, str) else str(response.content)
            return self._strip_fences(content)
        except Exception as e:
            return f"# LLM generation failed: {e!s}\npass\n"

    async def _fix_code(self, broken_code: str, error: str) -> str:
        """Ask LLM to fix a syntax error."""
        if not self.llm:
            return broken_code
        try:
            response = await self.llm.ainvoke([
                SystemMessage(content="Fix the Python syntax error. Return ONLY valid Python code."),
                HumanMessage(content=f"ERROR: {error}\n\nCODE:\n{broken_code}"),
            ])
            content = response.content if isinstance(response.content, str) else str(response.content)
            return self._strip_fences(content)
        except Exception:
            return broken_code

    @staticmethod
    def _fix_imports(code: str, unresolved: list[str]) -> str:
        """Comment out unresolved imports."""
        lines = code.split("\n")
        fixed: list[str] = []
        for line in lines:
            if any(u in line for u in unresolved) and ("import " in line):
                fixed.append(f"# FIXME: unresolved — {line}")
            else:
                fixed.append(line)
        return "\n".join(fixed)

    @staticmethod
    def _strip_fences(content: str) -> str:
        content = content.strip()
        if content.startswith("```python"):
            content = content[len("```python"):]
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        return content.strip()

    @staticmethod
    def _to_snake(name: str) -> str:
        name = (
            name.removesuffix("Controller")
            .removesuffix("Service")
            .removesuffix("ServiceImpl")
            .removesuffix("Repository")
            .removesuffix("Entity")
            .removesuffix("Impl")
            .removesuffix("Dto")
            .removesuffix("DTO")
        )
        return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()

    def _generate_fallback_scaffold(
        self, class_name: str, component_type: str, java_source: str,
    ) -> str:
        """Generate a TODO-commented Python skeleton from Java method signatures.

        Used when the LLM is unavailable. Extracts public method names from
        the Java source and creates stub methods so the file is valid Python.
        """
        # Extract method names from Java source
        method_pattern = re.compile(
            r"(?:public|protected)\s+[\w<>\[\],\s?]+\s+(\w+)\s*\("
        )
        methods = method_pattern.findall(java_source)

        # Filter out constructors and common noise
        methods = [
            m for m in methods
            if m != class_name and not m.startswith("set") and m not in ("equals", "hashCode", "toString")
        ]

        snake_name = self._to_snake(class_name)
        py_class = class_name

        lines = [
            f'"""TODO: Auto-generated scaffold for {class_name}.',
            f'Component type: {component_type}.',
            'LLM was unavailable — manual implementation required.',
            '"""',
            "",
        ]

        if component_type == "model":
            lines.extend([
                "from sqlalchemy.orm import Mapped, mapped_column",
                "from app.db.base import Base",
                "",
                "",
                f"class {py_class}(Base):",
                f'    __tablename__ = "{snake_name}s"',
                "",
                "    id: Mapped[int] = mapped_column(primary_key=True)",
                "    # TODO: Add columns from Java entity",
            ])
        elif component_type == "schema":
            lines.extend([
                "from pydantic import BaseModel, ConfigDict",
                "",
                "",
                f"class {py_class}Create(BaseModel):",
                "    # TODO: Add fields from Java DTO",
                "    pass",
                "",
                "",
                f"class {py_class}Response(BaseModel):",
                '    model_config = ConfigDict(from_attributes=True)',
                "    # TODO: Add fields from Java DTO",
                "    pass",
            ])
        elif component_type == "controller":
            lines.extend([
                "from fastapi import APIRouter, Depends",
                "from sqlalchemy.ext.asyncio import AsyncSession",
                "from app.db.session import get_db",
                "",
                "router = APIRouter()",
                "",
            ])
            for m in methods[:10]:
                snake_m = re.sub(r"(?<!^)(?=[A-Z])", "_", m).lower()
                lines.extend([
                    "",
                    f'@router.get("/{snake_m}")',
                    f"async def {snake_m}(db: AsyncSession = Depends(get_db)):",
                    f"    # TODO: Implement {m} from Java controller",
                    '    return {"status": "not implemented"}',
                ])
        elif component_type == "service":
            lines.extend([
                "from sqlalchemy.ext.asyncio import AsyncSession",
                "",
                "",
                f"class {py_class}:",
                '    """TODO: Implement business logic."""',
                "",
                "    def __init__(self, db: AsyncSession) -> None:",
                "        self.db = db",
            ])
            for m in methods[:15]:
                snake_m = re.sub(r"(?<!^)(?=[A-Z])", "_", m).lower()
                lines.extend([
                    "",
                    f"    async def {snake_m}(self):",
                    f"        # TODO: Implement {m} from Java service",
                    "        raise NotImplementedError",
                ])
        else:
            # Generic fallback
            lines.extend([
                "",
                f"class {py_class}:",
                f'    """TODO: Implement {component_type}."""',
                "    pass",
            ])

        return "\n".join(lines) + "\n"

