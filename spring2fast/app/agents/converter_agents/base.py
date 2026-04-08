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

import asyncio
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
        output_registry: dict[str, str],
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
            deterministic_code = self._deterministic_convert(
                component=component,
                java_ir=java_ir,
                java_source=java_source,
            )
            if deterministic_code:
                syntax_check = tools.validate_syntax(deterministic_code)
                if syntax_check["valid"]:
                    output_path = self._get_output_path(component)
                    deterministic_code = self._resolve_imports(
                        deterministic_code,
                        output_registry=output_registry,
                    )
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
                if not import_check["valid"]:
                    code = self._resolve_imports(
                        code,
                        output_registry=output_registry,
                        unresolved=import_check["unresolved"],
                    )

                # ── Check for stub/empty method bodies (SFS fix) ──
                if component_type in ("service", "controller", "repo"):
                    stub_methods = self._has_stub_methods(code)
                    if stub_methods:
                        if attempt < self.MAX_INNER_RETRIES:
                            error_msg = (
                                "INCOMPLETE: These methods have empty or stub bodies: "
                                + ", ".join(stub_methods)
                                + ". Re-implement them with real logic from the Java source and contract. "
                                  "Every method must contain working business logic, repository queries, "
                                  "or controller/service wiring. Do not use pass, return None, "
                                  "raise NotImplementedError, TODOs, or placeholder comments."
                            )
                            code = await self._fix_code(code, error_msg)
                            continue
                        result.error = (
                            "Incomplete implementation: stub methods remain after retries: "
                            + ", ".join(stub_methods)
                        )
                        result.code = code
                        break

                # Passed inner validation
                output_path = self._get_output_path(component)
                code = self._resolve_imports(
                    code,
                    output_registry=output_registry,
                )
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

    def _deterministic_convert(
        self,
        *,
        component: dict[str, Any],
        java_ir: dict[str, Any],
        java_source: str,
    ) -> str | None:
        return tools.deterministic_convert(self._get_component_type(), java_ir)

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
                    "No markdown fences, no explanations, no commentary. "
                    "IMPORTANT: The Python package root is 'app'. "
                    "All internal imports MUST use 'from app.' or 'import app.'. "
                    "NEVER use placeholder names like 'yourapp', 'myapp', 'project', or 'src' in imports."
                )),
                HumanMessage(content=prompt),
            ])
            content = response.content if isinstance(response.content, str) else str(response.content)
            return self._strip_fences(self._sanitize_imports(content))
        except asyncio.CancelledError:
            # Groq/API rate limit retry was cancelled — don't crash the pipeline
            return "# LLM call cancelled (rate limit/timeout) — manual conversion needed\npass\n"
        except Exception as e:
            error_str = str(e).lower()
            if "rate" in error_str or "429" in error_str or "quota" in error_str:
                return f"# LLM rate limited: {e!s}\n# TODO: Retry later or switch LLM provider\npass\n"
            return f"# LLM generation failed: {e!s}\npass\n"

    async def _fix_code(self, broken_code: str, error: str) -> str:
        """Ask LLM to fix syntax or completeness issues."""
        if not self.llm:
            return broken_code
        try:
            response = await self.llm.ainvoke([
                SystemMessage(content=(
                    "Fix the Python code and return ONLY valid Python code. "
                    "Preserve all methods. If the error mentions incomplete or stub "
                    "implementations, replace every stub with a real implementation "
                    "grounded in the existing code and Java source intent."
                )),
                HumanMessage(content=f"ERROR: {error}\n\nCODE:\n{broken_code}"),
            ])
            content = response.content if isinstance(response.content, str) else str(response.content)
            return self._strip_fences(content)
        except Exception:
            return broken_code

    @staticmethod
    def _resolve_imports(
        code: str,
        *,
        output_registry: dict[str, str],
        unresolved: list[str] | None = None,
    ) -> str:
        """Resolve internal imports against the generated output registry.

        Falls back to commenting the import only when the imported symbol does
        not exist anywhere in the known registry.
        """
        unresolved = unresolved or []
        lines = code.split("\n")
        fixed: list[str] = []

        for line in lines:
            stripped = line.strip()
            if "import " not in stripped or not (stripped.startswith("from ") or stripped.startswith("import ")):
                fixed.append(line)
                continue

            updated = line
            from_match = re.match(r"^(\s*)from\s+([A-Za-z0-9_\.]+)\s+import\s+(.+)$", line)
            if from_match:
                indent, module, imported = from_match.groups()
                imported_names = [
                    part.split(" as ")[0].strip()
                    for part in imported.split(",")
                    if part.strip() and part.strip() != "*"
                ]
                replacement_module = module
                for imported_name in imported_names:
                    target = output_registry.get(imported_name)
                    if target:
                        replacement_module = target.removesuffix(".py").replace("/", ".")
                        break

                if replacement_module != module:
                    updated = f"{indent}from {replacement_module} import {imported}"
                elif any(item == module or item in line for item in unresolved):
                    missing = [name for name in imported_names if name not in output_registry]
                    if missing:
                        updated = f"{indent}# FIXME: unresolved - {stripped}"

            import_match = re.match(r"^(\s*)import\s+([A-Za-z0-9_\.]+)(\s+as\s+\w+)?$", line)
            if import_match:
                indent, module, alias = import_match.groups()
                module_name = module.split(".")[-1]
                class_like = "".join(part.capitalize() for part in module_name.split("_"))
                target = output_registry.get(class_like)
                if target:
                    replacement_module = target.removesuffix(".py").replace("/", ".")
                    updated = f"{indent}import {replacement_module}{alias or ''}"
                elif any(item == module or item in line for item in unresolved):
                    updated = f"{indent}# FIXME: unresolved - {stripped}"

            fixed.append(updated)

        return "\n".join(fixed)

    @staticmethod
    def _sanitize_imports(code: str) -> str:
        """Replace placeholder package names with the real 'app' package."""
        import re
        placeholders = ["yourapp", "myapp", "your_app", "my_app", "application", "project"]
        for placeholder in placeholders:
            # Replace in import statements only
            code = re.sub(
                rf'\b{re.escape(placeholder)}\b',
                'app',
                code,
            )
        return code

    @staticmethod
    def _has_stub_methods(code: str) -> list[str]:
        """Return names of methods whose bodies are pure stubs (pass / return None / raise NotImplementedError).

        Used by the inner validation loop to force LLM retry when generated code
        has correct syntax but empty implementations — which would tank the SFS score.
        """
        import ast as _ast

        stubs: list[str] = []
        try:
            tree = _ast.parse(code)
        except SyntaxError:
            return []

        for node in _ast.walk(tree):
            if not isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
                continue
            body = list(node.body)
            # Strip leading docstring
            if body and isinstance(body[0], _ast.Expr) and isinstance(body[0].value, _ast.Constant):
                body = body[1:]

            if not body:
                stubs.append(node.name)
                continue

            def _is_stub_stmt(stmt: _ast.stmt) -> bool:
                if isinstance(stmt, _ast.Pass):
                    return True
                if isinstance(stmt, _ast.Return) and (
                    stmt.value is None
                    or (isinstance(stmt.value, _ast.Constant) and stmt.value.value is None)
                ):
                    return True
                if isinstance(stmt, _ast.Raise) and stmt.exc is not None:
                    try:
                        unparsed = _ast.unparse(stmt.exc)
                        if "NotImplementedError" in unparsed or "NotImplemented" in unparsed:
                            return True
                    except Exception:
                        pass
                return False

            if all(_is_stub_stmt(s) for s in body):
                stubs.append(node.name)

        return stubs

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
