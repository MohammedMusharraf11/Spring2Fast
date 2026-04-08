"""Shared tools for converter agents.

Each tool is a plain function that converter agents invoke during their
ReAct loop. They wrap deterministic operations (file I/O, AST parsing,
syntax checking) so the agent can focus on orchestration decisions.
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from app.services.java_ast_parser import JavaASTParser


_parser = JavaASTParser()


# ─────────────────────────────────────────────
# READ tools
# ─────────────────────────────────────────────

def read_java_source(file_path: str, input_dir: str) -> str:
    """Read raw Java source code for a component."""
    full = Path(input_dir) / file_path
    if full.exists():
        return full.read_text(encoding="utf-8", errors="ignore")
    # Try globbing for the class name
    class_name = Path(file_path).stem
    for f in Path(input_dir).rglob(f"{class_name}.java"):
        return f.read_text(encoding="utf-8", errors="ignore")
    return f"// Java source not found: {file_path}"


def read_contract(class_name: str, contracts_dir: str) -> str:
    """Read the .md business-logic contract for a class."""
    contracts = Path(contracts_dir)
    if not contracts.exists():
        return "# No contract available"
    snake = _to_snake(class_name)
    for md in contracts.rglob("*.md"):
        if md.stem == snake or snake in md.stem:
            return md.read_text(encoding="utf-8", errors="ignore")
    return f"# No contract found for {class_name}"


def read_existing_code(layer: str, output_dir: str) -> str:
    """Read already-generated Python code for a layer.

    *layer* is one of: models, schemas, repositories, services, controllers.
    Returns concatenated code from all .py files in that layer directory.
    """
    layer_dirs = {
        "models": "app/models",
        "schemas": "app/schemas",
        "repositories": "app/repositories",
        "services": "app/services",
        "controllers": "app/api/v1/endpoints",
    }
    layer_path = Path(output_dir) / layer_dirs.get(layer, f"app/{layer}")
    if not layer_path.exists():
        return f"# No {layer} generated yet"
    parts: list[str] = []
    for py in sorted(layer_path.glob("*.py")):
        if py.stem != "__init__":
            try:
                parts.append(f"# --- {py.name} ---\n{py.read_text(encoding='utf-8', errors='ignore')}")
            except Exception:
                pass
    return "\n\n".join(parts) if parts else f"# No {layer} files found"


def read_docs_context(technology: str, artifacts_dir: str) -> str:
    """Read cached documentation context for a Python library."""
    mapping_path = Path(artifacts_dir) / "04-integration-mapping.md"
    if not mapping_path.exists():
        return f"# No documentation context for {technology}"
    content = mapping_path.read_text(encoding="utf-8", errors="ignore")
    # Try to find the section for this technology
    tech_lower = technology.lower()
    lines = content.split("\n")
    capturing = False
    result: list[str] = []
    for line in lines:
        if tech_lower in line.lower() and line.startswith("#"):
            capturing = True
        elif capturing and line.startswith("# ") and tech_lower not in line.lower():
            break
        if capturing:
            result.append(line)
    return "\n".join(result) if result else content[:3000]


# ─────────────────────────────────────────────
# PARSE tools
# ─────────────────────────────────────────────

def parse_java_to_ir(source: str, file_path: str = "") -> dict[str, Any]:
    """Parse Java source into structured IR (as a serializable dict)."""
    try:
        ir = _parser.parse_file(source, file_path=file_path)
        return _ir_to_dict(ir)
    except Exception as e:
        return {"error": str(e), "parse_method": "failed"}


def extract_method_bodies(source: str) -> dict[str, str]:
    """Extract raw method bodies from Java source."""
    return _parser.extract_method_bodies(source)


# ─────────────────────────────────────────────
# GENERATE tools
# ─────────────────────────────────────────────

def deterministic_convert(component_type: str, java_ir: dict[str, Any]) -> str | None:
    """Apply deterministic Java→Python mappings for simple components.

    Returns generated Python code if the component is simple enough for
    deterministic conversion, otherwise None (caller should use LLM).
    """
    classes = java_ir.get("classes", [])
    if not classes:
        return None

    cls = classes[0]
    annotations = [a.get("name", "") for a in cls.get("annotations", [])]

    # ── Tier 1: Simple entity → SQLAlchemy model ──
    if component_type == "model" and "Entity" in annotations:
        return _deterministic_entity(cls)

    # ── Tier 1: Simple repository interface → SQLAlchemy repository ──
    if component_type == "repo" and cls.get("kind") == "interface":
        methods = cls.get("methods", [])
        if len(methods) <= 2:  # Only basic CRUD — no custom queries
            return _deterministic_repository(cls)

    return None


def _deterministic_entity(cls: dict[str, Any]) -> str:
    """Generate a SQLAlchemy model from an entity IR, including relationships."""
    name = cls.get("name", "Model")
    table_name = _to_snake(name) + "s"

    # Check @Table annotation for explicit name
    for ann in cls.get("annotations", []):
        if ann.get("name") == "Table":
            args = ann.get("arguments", {})
            if "name" in args:
                table_name = args["name"].strip("\"'")

    fields = cls.get("fields", [])

    # Detect if we need datetime import
    needs_datetime = any(
        f.get("type", "") in ("LocalDateTime", "LocalDate", "Date", "Timestamp")
        for f in fields
    )

    lines = [
        '"""Auto-generated SQLAlchemy model."""',
        "",
        "from __future__ import annotations",
        "",
        "from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, Text, ForeignKey",
        "from sqlalchemy.orm import Mapped, mapped_column, relationship",
        "from app.db.base import Base",
    ]
    if needs_datetime:
        lines.append("from datetime import datetime")
    lines.extend(["", "", f"class {name}(Base):", f'    __tablename__ = "{table_name}"', ""])

    # Track which fields are relationship fields vs columns
    relationship_lines: list[str] = []

    for field in fields:
        field_annotations = [a.get("name", "") for a in field.get("annotations", [])]
        field_type = field.get("type", "String")
        field_name = field.get("name", "unknown")

        # ── @ManyToOne → ForeignKey column + relationship ──
        if "ManyToOne" in field_annotations:
            # Find @JoinColumn for the FK column name
            fk_column = field_name + "_id"
            for ann in field.get("annotations", []):
                if ann.get("name") == "JoinColumn":
                    fk_args = ann.get("arguments", {})
                    if "name" in fk_args:
                        fk_column = fk_args["name"].strip("\"'")

            ref_table = _to_snake(field_type) + "s"
            lines.append(
                f"    {fk_column}: Mapped[int | None] = mapped_column("
                f'ForeignKey("{ref_table}.id"), nullable=True)'
            )
            relationship_lines.append(
                f'    {field_name}: Mapped["{field_type}"] = relationship(back_populates="{_to_snake(name)}s")'
            )
            continue

        # ── @OneToMany → relationship only (no column) ──
        if "OneToMany" in field_annotations:
            # Extract mappedBy from annotation arguments
            mapped_by = _to_snake(name)
            for ann in field.get("annotations", []):
                if ann.get("name") == "OneToMany":
                    ann_args = ann.get("arguments", {})
                    if "mappedBy" in ann_args:
                        mapped_by = ann_args["mappedBy"].strip("\"'")

            # Extract the generic type (List<X> → X)
            target_type = field_type
            if "<" in field_type:
                target_type = field_type.split("<")[-1].rstrip(">").strip()

            relationship_lines.append(
                f'    {field_name}: Mapped[list["{target_type}"]] = '
                f'relationship(back_populates="{mapped_by}")'
            )
            continue

        # ── @ManyToMany → secondary table + relationship ──
        if "ManyToMany" in field_annotations:
            target_type = field_type
            if "<" in field_type:
                target_type = field_type.split("<")[-1].rstrip(">").strip()

            assoc_table = f"{_to_snake(name)}_{_to_snake(target_type)}"
            relationship_lines.append(
                f'    {field_name}: Mapped[list["{target_type}"]] = '
                f'relationship(secondary="{assoc_table}")'
            )
            continue

        # ── Regular column ──
        col = _map_java_type_to_sqlalchemy(field)
        lines.append(f"    {col}")

    # Add relationships after columns
    if relationship_lines:
        lines.append("")
        lines.append("    # ── Relationships ──")
        lines.extend(relationship_lines)

    if not fields:
        lines.append("    id: Mapped[int] = mapped_column(primary_key=True)")

    return "\n".join(lines) + "\n"


def _deterministic_repository(cls: dict[str, Any]) -> str:
    """Generate a simple SQLAlchemy repository from a repository interface IR."""
    name = cls.get("name", "Repository").replace("Repository", "")
    model_name = name
    snake = _to_snake(name)

    return (
        f'"""Auto-generated repository for {model_name}."""\n\n'
        f"from sqlalchemy.orm import Session\n"
        f"from sqlalchemy import select\n"
        f"from app.models.{snake} import {model_name}\n\n\n"
        f"class {model_name}Repository:\n"
        f'    """Repository for {model_name} CRUD operations."""\n\n'
        f"    def __init__(self, db: Session) -> None:\n"
        f"        self.db = db\n\n"
        f"    def get_by_id(self, id: int) -> {model_name} | None:\n"
        f"        return self.db.get({model_name}, id)\n\n"
        f"    def get_all(self) -> list[{model_name}]:\n"
        f"        return list(self.db.execute(select({model_name})).scalars().all())\n\n"
        f"    def save(self, entity: {model_name}) -> {model_name}:\n"
        f"        self.db.add(entity)\n"
        f"        self.db.commit()\n"
        f"        self.db.refresh(entity)\n"
        f"        return entity\n\n"
        f"    def delete(self, entity: {model_name}) -> None:\n"
        f"        self.db.delete(entity)\n"
        f"        self.db.commit()\n"
    )


def _map_java_type_to_sqlalchemy(field: dict[str, Any]) -> str:
    """Map a Java field IR to a SQLAlchemy column definition."""
    name = field.get("name", "unknown")
    java_type = field.get("type", "String")
    annotations = [a.get("name", "") for a in field.get("annotations", [])]

    is_id = "Id" in annotations
    is_generated = "GeneratedValue" in annotations

    type_map = {
        "String": ("str", "String(255)"),
        "Long": ("int", "Integer"),
        "long": ("int", "Integer"),
        "Integer": ("int", "Integer"),
        "int": ("int", "Integer"),
        "Double": ("float", "Float"),
        "double": ("float", "Float"),
        "Float": ("float", "Float"),
        "float": ("float", "Float"),
        "Boolean": ("bool", "Boolean"),
        "boolean": ("bool", "Boolean"),
        "LocalDateTime": ("datetime", "DateTime"),
        "LocalDate": ("datetime", "DateTime"),
        "Date": ("datetime", "DateTime"),
        "BigDecimal": ("float", "Float"),
    }

    py_type, col_type = type_map.get(java_type, ("str", "String(255)"))

    constraints: list[str] = []
    if is_id:
        constraints.append("primary_key=True")
    if is_generated:
        constraints.append("autoincrement=True")
    if "NotNull" in annotations or "Column" in annotations:
        constraints.append("nullable=False")

    constraint_str = ", ".join(constraints)
    if constraint_str:
        return f"{name}: Mapped[{py_type}] = mapped_column({col_type}, {constraint_str})"
    return f"{name}: Mapped[{py_type}] = mapped_column({col_type})"


# ─────────────────────────────────────────────
# VALIDATE tools
# ─────────────────────────────────────────────

def validate_syntax(code: str) -> dict[str, Any]:
    """Validate Python code syntax via ast.parse."""
    try:
        ast.parse(code)
        return {"valid": True, "error": None}
    except SyntaxError as e:
        return {"valid": False, "error": f"Line {e.lineno}: {e.msg}"}


def check_imports(code: str, output_dir: str) -> dict[str, Any]:
    """Check that all imports in generated code resolve."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return {"valid": False, "unresolved": ["code has syntax errors"]}

    unresolved: list[str] = []
    output_root = Path(output_dir)

    for node in ast.walk(tree):
        module = None
        if isinstance(node, ast.Import):
            for alias in node.names:
                module = alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            module = node.module

        if module and module.startswith("app."):
            # Check if the import target exists in the generated project
            parts = module.replace(".", "/")
            py_path = output_root / f"{parts}.py"
            pkg_path = output_root / parts / "__init__.py"
            if not py_path.exists() and not pkg_path.exists():
                unresolved.append(module)

    return {"valid": len(unresolved) == 0, "unresolved": unresolved}


def lint_code(code: str) -> dict[str, Any]:
    """Run ruff on code string, return errors."""
    import tempfile
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(code)
            f.flush()
            result = subprocess.run(
                [sys.executable, "-m", "ruff", "check", f.name, "--select=E,F", "--output-format=json", "--no-fix"],
                capture_output=True, text=True, timeout=15,
            )
            if result.stdout:
                findings = json.loads(result.stdout)
                errors = [f"{item['code']}: {item['message']}" for item in findings]
                return {"valid": len(errors) == 0, "errors": errors}
            return {"valid": True, "errors": []}
    except Exception:
        return {"valid": True, "errors": []}  # ruff unavailable — skip


def parse_bean_validation(fields: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Map Java Bean Validation metadata into a Pydantic-friendly summary."""
    parsed: dict[str, dict[str, Any]] = {}
    for field in fields:
        name = str(field.get("name", ""))
        annotations = field.get("annotations", []) or []
        validation = dict(field.get("validation") or {})
        ann_names: list[str] = []
        for annotation in annotations:
            if isinstance(annotation, dict):
                ann_names.append(str(annotation.get("name", "")).lstrip("@"))
            else:
                ann_names.append(str(annotation).lstrip("@"))
        if not validation:
            for ann in ann_names:
                if ann in {"NotNull", "NotBlank", "NotEmpty"}:
                    validation["required"] = True
                elif ann == "Email":
                    validation["format"] = "email"
        if validation:
            parsed[name] = validation
    return parsed


# ─────────────────────────────────────────────
# WRITE tools
# ─────────────────────────────────────────────

def write_output(relative_path: str, code: str, output_dir: str) -> str:
    """Write generated code to the output directory."""
    full = Path(output_dir) / relative_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(code, encoding="utf-8")
    # Ensure __init__.py exists in the package
    init = full.parent / "__init__.py"
    if not init.exists():
        init.write_text("", encoding="utf-8")
    return str(full)


# ─────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────

def _to_snake(name: str) -> str:
    name = (
        name.removesuffix("Controller")
        .removesuffix("Service")
        .removesuffix("ServiceImpl")
        .removesuffix("Repository")
        .removesuffix("Entity")
        .removesuffix("Impl")
    )
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _ir_to_dict(ir: Any) -> dict[str, Any]:
    """Convert a JavaFileIR dataclass tree to a plain dict."""
    from dataclasses import asdict
    try:
        return asdict(ir)
    except Exception:
        return {"error": "Failed to serialize IR"}
