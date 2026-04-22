"""Lightweight validation service for generated FastAPI code.

Runs three fast, zero-dependency checks:
  1. Python syntax  — ast.parse() on every generated .py file
  2. Import resolution — every import resolves to stdlib / requirements / generated module
  3. Core files present — app/main.py and requirements.txt must exist
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Standard library top-level module names (Python 3.11+)
# ---------------------------------------------------------------------------
_STDLIB_MODULES = {
    "abc", "argparse", "array", "ast", "asyncio", "atexit", "base64",
    "bisect", "builtins", "bz2", "calendar", "cmath", "cmd", "code",
    "codecs", "collections", "colorsys", "concurrent", "configparser",
    "contextlib", "contextvars", "copy", "csv", "dataclasses", "datetime",
    "decimal", "difflib", "dis", "email", "enum", "errno", "functools",
    "gc", "glob", "gzip", "hashlib", "heapq", "hmac", "html", "http",
    "importlib", "inspect", "io", "ipaddress", "itertools", "json",
    "keyword", "linecache", "locale", "logging", "math", "multiprocessing",
    "operator", "os", "pathlib", "pickle", "platform", "pprint", "queue",
    "random", "re", "runpy", "secrets", "select", "shelve", "shlex",
    "shutil", "signal", "site", "socket", "sqlite3", "ssl", "stat",
    "statistics", "string", "struct", "subprocess", "sys", "tarfile",
    "tempfile", "textwrap", "threading", "time", "timeit", "tkinter",
    "token", "tokenize", "tomllib", "traceback", "types", "typing",
    "unicodedata", "unittest", "urllib", "uuid", "venv", "warnings",
    "weakref", "webbrowser", "xml", "xmlrpc", "zipfile", "zipimport",
    "zlib", "_thread", "_io", "_collections_abc", "typing_extensions",
}

# Map pip package names → importable top-level module names
_PACKAGE_TO_MODULE: dict[str, set[str]] = {
    "fastapi":                  {"fastapi"},
    "uvicorn":                  {"uvicorn"},
    "pydantic":                 {"pydantic"},
    "pydantic-settings":        {"pydantic_settings"},
    "python-dotenv":            {"dotenv"},
    "sqlalchemy":               {"sqlalchemy"},
    "alembic":                  {"alembic"},
    "asyncpg":                  {"asyncpg"},
    "psycopg2-binary":          {"psycopg2"},
    "pymysql":                  {"pymysql"},
    "aiomysql":                 {"aiomysql"},
    "motor":                    {"motor"},
    "pymongo":                  {"pymongo"},
    "redis":                    {"redis"},
    "aiokafka":                 {"aiokafka"},
    "aio-pika":                 {"aio_pika"},
    "python-jose":              {"jose"},
    "python-jose[cryptography]": {"jose"},
    "passlib":                  {"passlib"},
    "passlib[bcrypt]":          {"passlib"},
    "httpx":                    {"httpx"},
    "supabase":                 {"supabase"},
    "boto3":                    {"boto3"},
    "google-cloud-storage":     {"google"},
    "azure-storage-blob":       {"azure"},
    "pyjwt":                    {"jwt"},
    "starlette":                {"starlette"},
    "aiosqlite":                {"aiosqlite"},
}


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class ValidationResult:
    """Structured output from generated code validation."""

    artifact_path: Path
    validation_errors: list[str]
    warnings: list[str] = field(default_factory=list)
    is_successful: bool = True
    checks_passed: dict[str, bool] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class ValidationService:
    """Fast, dependency-free validation for generated FastAPI code."""

    async def validate(
        self,
        *,
        output_dir: str,
        artifacts_dir: str,
        business_rules: list[str] | None = None,
        contracts_dir: str | None = None,
        component_inventory: dict[str, list[dict[str, Any]]] | None = None,
    ) -> ValidationResult:
        """Run all checks and write a Markdown report artifact."""
        output_root = Path(output_dir)
        artifact_dir = Path(artifacts_dir)
        artifact_dir.mkdir(parents=True, exist_ok=True)

        all_errors: list[str] = []
        warnings: list[str] = []
        checks: dict[str, bool] = {}

        # ── Check 1: Python syntax ──────────────────────────────────────
        syntax_errors = self._check_syntax(output_root)
        checks["syntax"] = len(syntax_errors) == 0
        all_errors.extend(syntax_errors)

        # ── Check 2: Import resolution ──────────────────────────────────
        import_errors = self._check_imports(output_root)
        checks["imports"] = len(import_errors) == 0
        # Import errors are warnings — don't hard-fail the build, just report
        warnings.extend(import_errors)

        # ── Check 3: Core files present ─────────────────────────────────
        core_errors = self._check_core_files(output_root)
        checks["core_files"] = len(core_errors) == 0
        all_errors.extend(core_errors)

        is_successful = checks["syntax"] and checks["core_files"]

        # Write report
        artifact_path = artifact_dir / "08-validation-report.md"
        artifact_path.write_text(
            self._render_markdown(
                errors=all_errors,
                warnings=warnings,
                is_successful=is_successful,
                checks=checks,
            ),
            encoding="utf-8",
        )

        return ValidationResult(
            artifact_path=artifact_path,
            validation_errors=all_errors,
            warnings=warnings,
            is_successful=is_successful,
            checks_passed=checks,
        )

    # -----------------------------------------------------------------------
    # Check 1: Syntax
    # -----------------------------------------------------------------------

    def _check_syntax(self, output_dir: Path) -> list[str]:
        """Verify every generated .py file parses without SyntaxError."""
        errors: list[str] = []
        for py_file in output_dir.rglob("*.py"):
            try:
                source = py_file.read_text(encoding="utf-8", errors="ignore")
                ast.parse(source)
            except SyntaxError as e:
                rel = py_file.relative_to(output_dir)
                errors.append(f"[SYNTAX] {rel}:{e.lineno} — {e.msg}")
        return errors

    # -----------------------------------------------------------------------
    # Check 2: Import resolution
    # -----------------------------------------------------------------------

    def _check_imports(self, output_dir: Path) -> list[str]:
        """Warn about imports that cannot be resolved statically."""
        generated = self._build_module_index(output_dir)
        requirements = self._parse_requirements(output_dir / "requirements.txt")
        errors: list[str] = []

        for py_file in output_dir.rglob("*.py"):
            try:
                source = py_file.read_text(encoding="utf-8", errors="ignore")
                tree = ast.parse(source)
            except (SyntaxError, UnicodeDecodeError):
                continue  # Already caught by syntax check

            rel = py_file.relative_to(output_dir)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if not self._can_resolve(alias.name, generated, requirements):
                            errors.append(f"[IMPORT] Unresolved '{alias.name}' in {rel}")
                elif isinstance(node, ast.ImportFrom) and node.module:
                    if not self._can_resolve(node.module, generated, requirements):
                        errors.append(f"[IMPORT] Unresolved '{node.module}' in {rel}")
        return errors

    def _build_module_index(self, output_dir: Path) -> set[str]:
        """Return all dotted module paths present in the generated project."""
        modules: set[str] = set()
        for py_file in output_dir.rglob("*.py"):
            rel = py_file.relative_to(output_dir)
            parts = list(rel.parts)
            if parts[-1] == "__init__.py":
                parts = parts[:-1]
            else:
                parts[-1] = parts[-1].removesuffix(".py")
            for i in range(len(parts)):
                modules.add(".".join(parts[: i + 1]))
        return modules

    def _parse_requirements(self, req_path: Path) -> set[str]:
        """Parse requirements.txt → set of importable top-level module names."""
        modules: set[str] = set()
        if not req_path.exists():
            return modules
        for line in req_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            pkg = (
                line.split(">=")[0].split("<=")[0].split("==")[0]
                    .split("<")[0].split(">")[0].split("[")[0].strip()
            ).lower()
            if pkg in _PACKAGE_TO_MODULE:
                modules.update(_PACKAGE_TO_MODULE[pkg])
            else:
                modules.add(pkg.replace("-", "_"))
        return modules

    def _can_resolve(self, module_path: str, generated: set[str], requirements: set[str]) -> bool:
        top = module_path.split(".")[0]
        return (
            module_path in generated
            or top in generated
            or top in _STDLIB_MODULES
            or top in requirements
            or top in {"__future__", "typing_extensions", "app"}
        )

    # -----------------------------------------------------------------------
    # Check 3: Core files
    # -----------------------------------------------------------------------

    def _check_core_files(self, output_dir: Path) -> list[str]:
        errors: list[str] = []
        for rel in ("app/main.py", "requirements.txt"):
            if not (output_dir / rel).exists():
                errors.append(f"[CORE] Missing required file: {rel}")
        return errors

    # -----------------------------------------------------------------------
    # Report
    # -----------------------------------------------------------------------

    def _render_markdown(
        self,
        *,
        errors: list[str],
        warnings: list[str],
        is_successful: bool,
        checks: dict[str, bool],
    ) -> str:
        status = "✅ PASSED" if is_successful else "❌ FAILED"
        check_rows = "\n".join(
            f"| {name} | {'✅ Pass' if ok else '❌ Fail'} |"
            for name, ok in checks.items()
        )
        errors_text = "\n".join(f"- {e}" for e in errors) or "None"
        warnings_text = "\n".join(f"- {w}" for w in warnings) or "None"
        return (
            f"# {status} — Validation Report\n\n"
            "## Checks\n\n"
            "| Check | Status |\n"
            "|-------|--------|\n"
            f"{check_rows}\n\n"
            "## Errors\n\n"
            f"{errors_text}\n\n"
            "## Import Warnings\n\n"
            f"{warnings_text}\n"
        )
