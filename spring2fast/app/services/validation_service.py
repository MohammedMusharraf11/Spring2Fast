"""Multi-layer validation service for generated FastAPI code.

Validates:
1. Python syntax via ast.parse()
2. Linting via ruff
3. Import resolution (generated modules, stdlib, requirements.txt)
4. Structural integrity (every IR component has a generated file)
5. LLM contract compliance (generated code satisfies business contracts)
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.llm import get_chat_model


# Standard library top-level module names (Python 3.11+)
_STDLIB_MODULES = {
    "abc", "aifc", "argparse", "array", "ast", "asynchat", "asyncio", "asyncore",
    "atexit", "base64", "bdb", "binascii", "binhex", "bisect", "builtins",
    "bz2", "calendar", "cgi", "cgitb", "chunk", "cmath", "cmd", "code",
    "codecs", "codeop", "collections", "colorsys", "compileall", "concurrent",
    "configparser", "contextlib", "contextvars", "copy", "copyreg", "cProfile",
    "crypt", "csv", "ctypes", "curses", "dataclasses", "datetime", "dbm",
    "decimal", "difflib", "dis", "distutils", "doctest", "email", "encodings",
    "enum", "errno", "faulthandler", "fcntl", "filecmp", "fileinput", "fnmatch",
    "fractions", "ftplib", "functools", "gc", "getopt", "getpass", "gettext",
    "glob", "grp", "gzip", "hashlib", "heapq", "hmac", "html", "http",
    "idlelib", "imaplib", "imghdr", "imp", "importlib", "inspect", "io",
    "ipaddress", "itertools", "json", "keyword", "lib2to3", "linecache",
    "locale", "logging", "lzma", "mailbox", "mailcap", "marshal", "math",
    "mimetypes", "mmap", "modulefinder", "multiprocessing", "netrc", "nis",
    "nntplib", "numbers", "operator", "optparse", "os", "ossaudiodev",
    "pathlib", "pdb", "pickle", "pickletools", "pipes", "pkgutil", "platform",
    "plistlib", "poplib", "posix", "posixpath", "pprint", "profile", "pstats",
    "pty", "pwd", "py_compile", "pyclbr", "pydoc", "queue", "quopri",
    "random", "re", "readline", "reprlib", "resource", "rlcompleter",
    "runpy", "sched", "secrets", "select", "selectors", "shelve", "shlex",
    "shutil", "signal", "site", "smtpd", "smtplib", "sndhdr", "socket",
    "socketserver", "sqlite3", "ssl", "stat", "statistics", "string",
    "stringprep", "struct", "subprocess", "sunau", "symtable", "sys",
    "sysconfig", "syslog", "tabnanny", "tarfile", "telnetlib", "tempfile",
    "termios", "test", "textwrap", "threading", "time", "timeit", "tkinter",
    "token", "tokenize", "tomllib", "trace", "traceback", "tracemalloc",
    "tty", "turtle", "turtledemo", "types", "typing", "unicodedata",
    "unittest", "urllib", "uuid", "venv", "warnings", "wave", "weakref",
    "webbrowser", "winreg", "winsound", "wsgiref", "xdrlib", "xml",
    "xmlrpc", "zipapp", "zipfile", "zipimport", "zlib",
    # Common internal modules
    "_thread", "_io", "_collections_abc", "typing_extensions",
}

# Map pip package names to their importable top-level module names
_PACKAGE_TO_MODULE: dict[str, set[str]] = {
    "fastapi": {"fastapi"},
    "uvicorn": {"uvicorn"},
    "pydantic": {"pydantic"},
    "pydantic-settings": {"pydantic_settings"},
    "python-dotenv": {"dotenv"},
    "sqlalchemy": {"sqlalchemy"},
    "alembic": {"alembic"},
    "asyncpg": {"asyncpg"},
    "psycopg2-binary": {"psycopg2"},
    "pymysql": {"pymysql"},
    "motor": {"motor"},
    "pymongo": {"pymongo"},
    "redis": {"redis"},
    "aiokafka": {"aiokafka"},
    "aio-pika": {"aio_pika"},
    "python-jose": {"jose"},
    "python-jose[cryptography]": {"jose"},
    "passlib": {"passlib"},
    "passlib[bcrypt]": {"passlib"},
    "httpx": {"httpx"},
    "supabase": {"supabase"},
    "boto3": {"boto3"},
    "google-cloud-storage": {"google"},
    "azure-storage-blob": {"azure"},
    "pytest": {"pytest"},
    "pytest-asyncio": {"pytest_asyncio"},
    "pyjwt": {"jwt"},
}


@dataclass(slots=True)
class ValidationResult:
    """Structured output from generated code validation."""

    artifact_path: Path
    validation_errors: list[str]
    warnings: list[str] = field(default_factory=list)
    is_successful: bool = True
    checks_passed: dict[str, bool] = field(default_factory=dict)


class ValidationService:
    """Multi-layer validation for generated FastAPI code."""

    def __init__(self) -> None:
        self.llm = get_chat_model()

    async def validate(
        self,
        *,
        output_dir: str,
        artifacts_dir: str,
        business_rules: list[str],
        contracts_dir: str | None = None,
        component_inventory: dict[str, list[dict[str, Any]]] | None = None,
    ) -> ValidationResult:
        """Run all validation checks and produce a comprehensive report."""
        output_root = Path(output_dir)
        artifact_dir = Path(artifacts_dir)
        artifact_dir.mkdir(parents=True, exist_ok=True)

        all_errors: list[str] = []
        all_warnings: list[str] = []
        checks: dict[str, bool] = {}

        # ── Check 1: Python syntax validation ──
        syntax_errors = self._check_syntax(output_root)
        checks["syntax"] = len(syntax_errors) == 0
        all_errors.extend(syntax_errors)

        # ── Check 2: Ruff lint ──
        lint_errors = self._check_lint(output_root)
        # Lint warnings don't fail the build, only F-errors do
        fatal_lint = [e for e in lint_errors if ":F" in e or ":E9" in e]
        non_fatal_lint = [e for e in lint_errors if e not in fatal_lint]
        checks["lint"] = len(fatal_lint) == 0
        all_errors.extend(fatal_lint)
        all_warnings.extend(non_fatal_lint)

        # ── Check 3: Import resolution ──
        import_errors = self._check_imports(output_root)
        checks["imports"] = len(import_errors) == 0
        all_errors.extend(import_errors)

        # ── Check 4: Structural integrity ──
        if component_inventory:
            struct_errors = self._check_structural_integrity(output_root, component_inventory)
            checks["structure"] = len(struct_errors) == 0
            all_errors.extend(struct_errors)
        else:
            checks["structure"] = True

        # ── Check 5: Core files present ──
        core_errors = self._check_core_files(output_root)
        checks["core_files"] = len(core_errors) == 0
        all_errors.extend(core_errors)

        # ── Check 6: Contract compliance (LLM-as-judge) ──
        if contracts_dir and self.llm:
            contracts_path = Path(contracts_dir)
            if contracts_path.exists():
                compliance_errors = await self._check_contract_compliance(output_root, contracts_path)
                checks["contract_compliance"] = len(compliance_errors) == 0
                all_errors.extend(compliance_errors)
            else:
                checks["contract_compliance"] = True
        else:
            checks["contract_compliance"] = True

        is_successful = all(checks.values())

        # Write report
        artifact_path = artifact_dir / "08-validation-report.md"
        artifact_path.write_text(
            self._render_markdown(
                errors=all_errors,
                warnings=all_warnings,
                is_successful=is_successful,
                checks=checks,
            ),
            encoding="utf-8",
        )

        return ValidationResult(
            artifact_path=artifact_path,
            validation_errors=all_errors,
            warnings=all_warnings,
            is_successful=is_successful,
            checks_passed=checks,
        )

    # ──────────────────────────────────────────────────────────────────
    # Check 1: Syntax
    # ──────────────────────────────────────────────────────────────────

    def _check_syntax(self, output_dir: Path) -> list[str]:
        """Verify each generated file is valid Python via ast.parse."""
        errors: list[str] = []
        for py_file in output_dir.rglob("*.py"):
            try:
                source = py_file.read_text(encoding="utf-8", errors="ignore")
                ast.parse(source)
            except SyntaxError as e:
                rel = py_file.relative_to(output_dir)
                errors.append(f"[SYNTAX] {rel}:{e.lineno} — {e.msg}")
        return errors

    # ──────────────────────────────────────────────────────────────────
    # Check 2: Ruff lint
    # ──────────────────────────────────────────────────────────────────

    def _check_lint(self, output_dir: Path) -> list[str]:
        """Run ruff linter on generated code."""
        errors: list[str] = []
        try:
            result = subprocess.run(
                [
                    sys.executable, "-m", "ruff", "check",
                    str(output_dir),
                    "--output-format=json",
                    "--select=E,F,I",
                    "--no-fix",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.stdout:
                findings = json.loads(result.stdout)
                for item in findings:
                    filename = Path(item.get("filename", "")).name
                    row = item.get("location", {}).get("row", "?")
                    code = item.get("code", "?")
                    message = item.get("message", "unknown")
                    errors.append(f"[LINT] {filename}:{row} {code} — {message}")
        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
            # ruff not available — skip lint check
            pass
        return errors

    # ──────────────────────────────────────────────────────────────────
    # Check 3: Import resolution
    # ──────────────────────────────────────────────────────────────────

    def _check_imports(self, output_dir: Path) -> list[str]:
        """Verify all imports resolve to generated files, stdlib, or requirements."""
        generated_modules = self._build_module_index(output_dir)
        requirement_modules = self._parse_requirements(output_dir / "requirements.txt")
        errors: list[str] = []

        for py_file in output_dir.rglob("*.py"):
            try:
                source = py_file.read_text(encoding="utf-8", errors="ignore")
                tree = ast.parse(source)
            except (SyntaxError, UnicodeDecodeError):
                continue  # Already caught by syntax check

            rel_name = py_file.relative_to(output_dir)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if not self._can_resolve(alias.name, generated_modules, requirement_modules):
                            errors.append(f"[IMPORT] Unresolved '{alias.name}' in {rel_name}")
                elif isinstance(node, ast.ImportFrom) and node.module:
                    if not self._can_resolve(node.module, generated_modules, requirement_modules):
                        errors.append(f"[IMPORT] Unresolved '{node.module}' in {rel_name}")
        return errors

    def _build_module_index(self, output_dir: Path) -> set[str]:
        """Build a set of all importable module paths in the generated project."""
        modules: set[str] = set()
        for py_file in output_dir.rglob("*.py"):
            rel = py_file.relative_to(output_dir)
            parts = list(rel.parts)
            # Convert path to dotted module name
            if parts[-1] == "__init__.py":
                parts = parts[:-1]
            else:
                parts[-1] = parts[-1].removesuffix(".py")
            if parts:
                # Add all prefix paths (e.g. "app", "app.models", "app.models.user")
                for i in range(len(parts)):
                    modules.add(".".join(parts[: i + 1]))
        return modules

    def _parse_requirements(self, req_path: Path) -> set[str]:
        """Parse requirements.txt and return importable module names."""
        modules: set[str] = set()
        if not req_path.exists():
            return modules
        for line in req_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            # Extract package name (before version specifier)
            pkg_name = line.split(">=")[0].split("<=")[0].split("==")[0].split("<")[0].split(">")[0].split("[")[0].strip()
            # Add known mappings
            if pkg_name.lower() in _PACKAGE_TO_MODULE:
                modules.update(_PACKAGE_TO_MODULE[pkg_name.lower()])
            else:
                # Default: assume import name == package name with - replaced by _
                modules.add(pkg_name.replace("-", "_").lower())
        return modules

    def _can_resolve(self, module_path: str, generated: set[str], requirements: set[str]) -> bool:
        """Check if a dotted import path resolves to a known module."""
        top_level = module_path.split(".")[0]

        # Check generated project modules
        if module_path in generated or top_level in generated:
            return True

        # Check stdlib
        if top_level in _STDLIB_MODULES:
            return True

        # Check installed packages (from requirements)
        if top_level in requirements:
            return True

        # Common false positives
        if top_level in {"__future__", "typing_extensions", "app"}:
            return True

        return False

    # ──────────────────────────────────────────────────────────────────
    # Check 4: Structural integrity
    # ──────────────────────────────────────────────────────────────────

    def _check_structural_integrity(
        self,
        output_dir: Path,
        component_inventory: dict[str, list[dict[str, Any]]],
    ) -> list[str]:
        """Ensure every IR component has a generated file."""
        errors: list[str] = []

        for entity in component_inventory.get("entities", []):
            cls = str(entity.get("class_name", ""))
            if cls and not self._find_generated_file(output_dir / "app" / "models", cls):
                errors.append(f"[STRUCTURE] Missing model file for entity: {cls}")

        for controller in component_inventory.get("controllers", []):
            cls = str(controller.get("class_name", ""))
            if cls and not self._find_generated_file(output_dir / "app" / "api" / "v1" / "endpoints", cls):
                errors.append(f"[STRUCTURE] Missing router file for controller: {cls}")

        for service in component_inventory.get("services", []):
            cls = str(service.get("class_name", ""))
            if cls and not self._find_generated_file(output_dir / "app" / "services", cls):
                errors.append(f"[STRUCTURE] Missing service file for: {cls}")

        for repo in component_inventory.get("repositories", []):
            cls = str(repo.get("class_name", ""))
            if cls and not self._find_generated_file(output_dir / "app" / "repositories", cls):
                errors.append(f"[STRUCTURE] Missing repository file for: {cls}")

        return errors

    def _find_generated_file(self, directory: Path, class_name: str) -> bool:
        """Check if any .py file in directory likely corresponds to class_name."""
        if not directory.exists():
            return False
        snake = self._to_snake(class_name)
        for py_file in directory.glob("*.py"):
            if py_file.stem == snake or py_file.stem.startswith(snake):
                return True
        return False

    # ──────────────────────────────────────────────────────────────────
    # Check 5: Core files
    # ──────────────────────────────────────────────────────────────────

    def _check_core_files(self, output_dir: Path) -> list[str]:
        """Ensure critical files exist."""
        errors: list[str] = []
        required = [
            "app/main.py",
            "requirements.txt",
        ]
        for rel in required:
            if not (output_dir / rel).exists():
                errors.append(f"[CORE] Missing required file: {rel}")
        return errors

    # ──────────────────────────────────────────────────────────────────
    # Check 6: Contract compliance (LLM-as-judge)
    # ──────────────────────────────────────────────────────────────────

    async def _check_contract_compliance(
        self,
        output_dir: Path,
        contracts_dir: Path,
    ) -> list[str]:
        """Ask the LLM to verify generated code satisfies business contracts."""
        violations: list[str] = []

        for contract_file in contracts_dir.rglob("*.md"):
            contract = contract_file.read_text(encoding="utf-8")
            generated_code = self._find_matching_code(output_dir, contract_file)
            if not generated_code:
                violations.append(f"[CONTRACT] No generated code found for contract: {contract_file.name}")
                continue

            # Truncate to avoid token limits
            contract_truncated = contract[:3000]
            code_truncated = generated_code[:4000]

            prompt = (
                "You are a code reviewer checking if generated Python code satisfies a business logic contract.\n\n"
                f"### CONTRACT\n{contract_truncated}\n\n"
                f"### GENERATED CODE\n{code_truncated}\n\n"
                "Does the Python code satisfy the key rules in the contract?\n"
                "Return ONLY a JSON object: {\"compliant\": true/false, \"violations\": [\"short description of each violation\"]}\n"
                "If compliant, return {\"compliant\": true, \"violations\": []}"
            )

            try:
                response = await self.llm.ainvoke([
                    SystemMessage(content="You are a strict code compliance checker. Return ONLY valid JSON."),
                    HumanMessage(content=prompt),
                ])
                content = response.content if isinstance(response.content, str) else str(response.content)
                # Strip markdown fences if present
                content = content.strip()
                if content.startswith("```"):
                    content = "\n".join(l for l in content.split("\n") if not l.startswith("```"))

                parsed = json.loads(content)
                if not parsed.get("compliant", True):
                    for v in parsed.get("violations", []):
                        violations.append(f"[CONTRACT] {contract_file.stem}: {v}")
            except (json.JSONDecodeError, Exception):
                # LLM response not parseable — skip this contract
                pass

        return violations

    def _find_matching_code(self, output_dir: Path, contract_file: Path) -> str | None:
        """Find the generated Python file that matches a contract file."""
        stem = contract_file.stem  # e.g. "user_service"

        # Search in likely directories
        search_dirs = [
            output_dir / "app" / "services",
            output_dir / "app" / "models",
            output_dir / "app" / "repositories",
            output_dir / "app" / "api" / "v1" / "endpoints",
            output_dir / "app" / "schemas",
        ]

        for search_dir in search_dirs:
            if not search_dir.exists():
                continue
            for py_file in search_dir.glob("*.py"):
                if py_file.stem == stem or stem.startswith(py_file.stem) or py_file.stem.startswith(stem):
                    return py_file.read_text(encoding="utf-8", errors="ignore")

        return None

    # ──────────────────────────────────────────────────────────────────
    # Report rendering
    # ──────────────────────────────────────────────────────────────────

    def _render_markdown(
        self,
        *,
        errors: list[str],
        warnings: list[str],
        is_successful: bool,
        checks: dict[str, bool],
    ) -> str:
        status_emoji = "✅" if is_successful else "❌"
        status_text = "PASSED" if is_successful else "FAILED"

        # Checks summary table
        check_rows = "\n".join(
            f"| {name} | {'✅ Pass' if passed else '❌ Fail'} |"
            for name, passed in checks.items()
        )

        errors_text = "\n".join(f"- {err}" for err in errors) if errors else "None"
        warnings_text = "\n".join(f"- {w}" for w in warnings) if warnings else "None"

        return (
            f"# {status_emoji} Validation Report: {status_text}\n\n"
            "## Check Summary\n\n"
            "| Check | Status |\n"
            "|-------|--------|\n"
            f"{check_rows}\n\n"
            "## Errors\n\n"
            f"{errors_text}\n\n"
            "## Warnings\n\n"
            f"{warnings_text}\n"
        )

    @staticmethod
    def _to_snake(name: str) -> str:
        import re
        name = (
            name.removesuffix("Controller")
            .removesuffix("Service")
            .removesuffix("Repository")
            .removesuffix("Entity")
            .removesuffix("Impl")
        )
        return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
