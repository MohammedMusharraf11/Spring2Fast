"""Business logic contract generator.

Replaces the flat rules list with structured per-service .md contract files
that feed into LLM synthesis and contract compliance validation.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage

from app.core.llm import get_chat_model
from app.services.java_ast_parser import JavaASTParser, JavaFileIR, ClassIR, MethodIR


class BusinessLogicContractService:
    """Generates per-component .md contract files from Java source."""

    def __init__(self) -> None:
        self.parser = JavaASTParser()
        self.llm = get_chat_model()

    def generate_contracts(
        self,
        *,
        input_dir: str,
        contracts_dir: str,
        component_inventory: dict[str, list[dict[str, Any]]],
    ) -> list[dict[str, str]]:
        """Generate .md contract files and return a manifest of what was created."""
        input_root = Path(input_dir)
        output_root = Path(contracts_dir)
        output_root.mkdir(parents=True, exist_ok=True)
        manifest: list[dict[str, str]] = []

        # Process each component category
        category_map = {
            "services": "services",
            "controllers": "api",
            "entities": "models",
            "repositories": "repositories",
        }

        for category, folder in category_map.items():
            components = component_inventory.get(category, [])
            folder_path = output_root / folder
            folder_path.mkdir(parents=True, exist_ok=True)

            for component in components:
                class_name = str(component.get("class_name", "Unknown"))
                java_path = component.get("file_path")
                java_source = ""
                if java_path:
                    full_path = input_root / str(java_path)
                    if full_path.exists():
                        java_source = full_path.read_text(encoding="utf-8", errors="ignore")

                file_ir = None
                if java_source:
                    try:
                        file_ir = self.parser.parse_file(java_source, file_path=str(java_path or ""))
                    except Exception:
                        file_ir = None

                contract_md = self._build_contract(
                    class_name=class_name,
                    category=category,
                    component=component,
                    file_ir=file_ir,
                    java_source=java_source,
                )

                snake_name = self._to_snake_case(class_name)
                contract_path = folder_path / f"{snake_name}.md"
                contract_path.write_text(contract_md, encoding="utf-8")

                manifest.append({
                    "contract_path": str(contract_path.relative_to(output_root)),
                    "source_class": class_name,
                    "category": category,
                    "java_path": str(java_path) if java_path else "",
                })

        return manifest

    def _build_contract(
        self,
        *,
        class_name: str,
        category: str,
        component: dict[str, Any],
        file_ir: JavaFileIR | None,
        java_source: str,
    ) -> str:
        """Build a structured .md contract for a single component."""
        sections: list[str] = [f"# {class_name} — Business Logic Contract\n"]

        # ── Class-level metadata ──
        class_ir: ClassIR | None = None
        if file_ir and file_ir.classes:
            class_ir = file_ir.classes[0]

        if class_ir:
            sections.append(f"**Kind:** {class_ir.kind}")
            if class_ir.extends:
                sections.append(f"**Extends:** `{class_ir.extends}`")
            if class_ir.implements:
                sections.append(f"**Implements:** {', '.join(f'`{i}`' for i in class_ir.implements)}")
            if class_ir.annotations:
                ann_str = ", ".join(f"@{a['name']}" for a in class_ir.annotations)
                sections.append(f"**Annotations:** {ann_str}")
            sections.append("")

        # ── Dependencies (from fields) ──
        deps = self._extract_dependencies(class_ir, component)
        if deps:
            sections.append("## Dependencies\n")
            for dep in deps:
                sections.append(f"- `{dep['type']}` ({dep['role']})")
            sections.append("")

        # ── Methods ──
        methods = self._extract_methods(class_ir, component)
        if methods:
            sections.append("## Methods\n")
            for method in methods:
                sections.append(f"### `{method['name']}`\n")
                sections.append(f"- **Signature:** `{method['signature']}`")
                sections.append(f"- **Return type:** `{method['return_type']}`")

                if method.get("annotations"):
                    sections.append(f"- **Annotations:** {', '.join(method['annotations'])}")

                # Business rules extracted from method body
                rules = method.get("rules", [])
                if rules:
                    sections.append("- **Business rules:**")
                    for rule in rules:
                        sections.append(f"  1. {rule}")

                # Side effects
                side_effects = method.get("side_effects", [])
                if side_effects:
                    sections.append("- **Side effects:**")
                    for effect in side_effects:
                        sections.append(f"  - {effect}")

                # Error conditions
                errors = method.get("errors", [])
                if errors:
                    sections.append("- **Error conditions:**")
                    sections.append("  | Condition | Exception | Action |")
                    sections.append("  |-----------|-----------|--------|")
                    for err in errors:
                        sections.append(f"  | {err['condition']} | `{err['exception']}` | {err.get('action', 'throw')} |")

                sections.append("")

        # ── Annotations summary ──
        annotation_summary = self._extract_annotation_summary(class_ir)
        if annotation_summary:
            sections.append("## Annotation Summary\n")
            for key, methods_list in annotation_summary.items():
                sections.append(f"- **{key}:** {', '.join(methods_list)}")
            sections.append("")

        return "\n".join(sections)

    def _extract_dependencies(
        self,
        class_ir: ClassIR | None,
        component: dict[str, Any],
    ) -> list[dict[str, str]]:
        """Extract injected dependencies from fields."""
        deps: list[dict[str, str]] = []
        if class_ir:
            for field in class_ir.fields:
                # Fields annotated with @Autowired, @Inject, or ending in Service/Repository
                is_injected = any(
                    a["name"] in ("Autowired", "Inject", "Resource", "Value")
                    for a in field.annotations
                )
                is_service_type = field.type.endswith(("Service", "Repository", "Client", "Template"))
                if is_injected or is_service_type:
                    role = "injected" if is_injected else "inferred dependency"
                    deps.append({"type": field.type, "name": field.name, "role": role})
        return deps

    def _extract_methods(
        self,
        class_ir: ClassIR | None,
        component: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Extract structured method information."""
        methods: list[dict[str, Any]] = []

        if class_ir:
            for m in class_ir.methods:
                param_strs = [f"{p.type} {p.name}" for p in m.parameters]
                signature = f"{m.return_type} {m.name}({', '.join(param_strs)})"
                annotations = [f"@{a['name']}" for a in m.annotations]

                # Extract rules from method body
                rules = self._extract_rules_from_body(m.body_source, m.name)
                side_effects = self._extract_side_effects(m.body_source)
                errors = self._extract_error_conditions(m.body_source)

                methods.append({
                    "name": m.name,
                    "signature": signature,
                    "return_type": m.return_type,
                    "annotations": annotations,
                    "rules": rules,
                    "side_effects": side_effects,
                    "errors": errors,
                })
        else:
            # Fallback: use raw method names from component dict
            raw_methods = component.get("methods", [])
            for name in raw_methods[:15]:
                methods.append({
                    "name": str(name),
                    "signature": f"? {name}(?)",
                    "return_type": "?",
                    "annotations": [],
                    "rules": [],
                    "side_effects": [],
                    "errors": [],
                })

        return methods

    def _extract_rules_from_body(self, body: str, method_name: str) -> list[str]:
        """Extract business rules from a method body via pattern matching."""
        if not body:
            return []
        rules: list[str] = []

        # Validation checks
        if_patterns = re.findall(r"if\s*\(([^)]{5,80})\)", body)
        for condition in if_patterns[:5]:
            condition = condition.strip()
            if any(kw in condition.lower() for kw in ("null", "empty", "blank", "size", "length", "valid", "exist")):
                rules.append(f"Validates: `{condition}`")

        # Data persistence
        if re.search(r"\.(save|persist|merge|insert|update)\s*\(", body):
            rules.append("Persists data to the database")
        if re.search(r"\.(delete|remove|deleteById)\s*\(", body):
            rules.append("Deletes data from the database")
        if re.search(r"\.(find|get|load|fetch|query|select|search)\w*\s*\(", body):
            rules.append("Queries existing data from the database")

        # Transformations
        if re.search(r"\.stream\(\)", body):
            rules.append("Uses Java Stream API for data transformation")
        if re.search(r"\.map\(", body):
            rules.append("Applies mapping/transformation to data")

        # Return patterns
        if "Optional" in body and "orElseThrow" in body:
            rules.append("Returns entity or throws not-found exception")

        return rules

    def _extract_side_effects(self, body: str) -> list[str]:
        """Extract side effects from a method body."""
        if not body:
            return []
        effects: list[str] = []

        if re.search(r"\.(send|publish|emit|dispatch|notify)\s*\(", body):
            effects.append("Sends event/message/notification")
        if re.search(r"(email|mail|smtp)", body, re.IGNORECASE):
            effects.append("Sends email")
        if re.search(r"\.(put|set|evict|invalidate)\s*\(.*[Cc]ache", body):
            effects.append("Modifies cache")
        if re.search(r"(log|logger|LOG)\.(info|warn|error|debug)", body):
            effects.append("Logs activity")
        if re.search(r"(httpClient|restTemplate|webClient|feign)\.", body, re.IGNORECASE):
            effects.append("Makes external HTTP call")

        return effects

    def _extract_error_conditions(self, body: str) -> list[dict[str, str]]:
        """Extract error/exception conditions from a method body."""
        if not body:
            return []
        errors: list[dict[str, str]] = []

        # throw new ExceptionType(...)
        throw_pattern = re.findall(
            r"throw\s+new\s+(\w+(?:Exception|Error)?)\s*\(([^)]*)\)", body
        )
        for exc_type, msg in throw_pattern[:5]:
            errors.append({
                "condition": msg.strip().strip("\"'")[:80] if msg.strip() else "unspecified",
                "exception": exc_type,
                "action": "throw",
            })

        # .orElseThrow(() -> new ...)
        or_else_pattern = re.findall(
            r"\.orElseThrow\(\s*\(\)\s*->\s*new\s+(\w+)\s*\(([^)]*)\)\)", body
        )
        for exc_type, msg in or_else_pattern[:3]:
            errors.append({
                "condition": msg.strip().strip("\"'")[:80] if msg.strip() else "entity not found",
                "exception": exc_type,
                "action": "throw",
            })

        return errors

    def _extract_annotation_summary(self, class_ir: ClassIR | None) -> dict[str, list[str]]:
        """Extract a summary of important annotations."""
        if not class_ir:
            return {}
        summary: dict[str, list[str]] = {}

        important_annotations = {
            "Transactional", "Cacheable", "CacheEvict", "CachePut",
            "Async", "Scheduled", "PreAuthorize", "Secured",
            "EventListener",
        }

        for method in class_ir.methods:
            for ann in method.annotations:
                if ann["name"] in important_annotations:
                    key = f"@{ann['name']}"
                    summary.setdefault(key, []).append(method.name)

        return summary

    @staticmethod
    def _to_snake_case(name: str) -> str:
        name = (
            name.removesuffix("Controller")
            .removesuffix("Service")
            .removesuffix("Repository")
            .removesuffix("ServiceImpl")
            .removesuffix("Impl")
            .removesuffix("Entity")
        )
        return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower() or name.lower()
