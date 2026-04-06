"""Generic Spring Boot component discovery."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


@dataclass(slots=True)
class ComponentDiscoveryResult:
    """Structured output for discovered Spring Boot components."""

    components: dict[str, list[dict[str, object]]]
    artifact_path: Path


class ComponentDiscoveryService:
    """Discovers Spring Boot component categories from Java source files."""

    CLASS_PATTERN = re.compile(r"class\s+([A-Za-z0-9_]+)")
    METHOD_PATTERN = re.compile(
        r"(public|private|protected)\s+[A-Za-z0-9_<>,\[\]\s]+\s+([A-Za-z0-9_]+)\s*\(",
    )
    METHOD_SIGNATURE_PATTERN = re.compile(
        r"(public|private|protected)\s+([A-Za-z0-9_<>,\[\]\s?]+?)\s+([A-Za-z0-9_]+)\s*\((.*?)\)\s*(?:\{|throws|$)",
    )
    FIELD_PATTERN = re.compile(
        r"(private|protected|public)\s+(?!class\b|interface\b|enum\b)(?:final\s+)?([A-Za-z0-9_<>,\[\]\.?]+)\s+([A-Za-z0-9_]+)\s*(?:=\s*[^;]+)?;",
    )
    REQUEST_MAPPING_PATTERN = re.compile(r'@(?:RequestMapping|GetMapping|PostMapping|PutMapping|DeleteMapping)\s*\((.*?)\)')

    CATEGORY_RULES = {
        "controllers": ["@RestController", "@Controller"],
        "services": ["@Service"],
        "repositories": ["@Repository"],
        "entities": ["@Entity"],
        "dtos": ["dto"],
        "exception_handlers": ["@ControllerAdvice", "@RestControllerAdvice"],
        "security": ["SecurityFilterChain", "@EnableWebSecurity", "WebSecurityConfigurerAdapter"],
        "configs": ["@Configuration"],
    }

    def discover(self, *, input_dir: str, artifacts_dir: str) -> ComponentDiscoveryResult:
        """Discover Spring Boot components and write a normalized artifact."""
        source_root = Path(input_dir)
        artifact_dir = Path(artifacts_dir)
        artifact_dir.mkdir(parents=True, exist_ok=True)

        components: dict[str, list[dict[str, object]]] = {key: [] for key in self.CATEGORY_RULES}

        for file_path in source_root.rglob("*.java"):
            if ".git" in file_path.parts:
                continue
            text = file_path.read_text(encoding="utf-8", errors="ignore")
            category = self._classify_component(file_path, text)
            if not category:
                continue

            class_name = self._extract_class_name(text) or file_path.stem
            class_annotations, fields, method_details = self._extract_structure(text)
            methods = [item["name"] for item in method_details]
            request_mappings = self._extract_request_mappings(text)
            components[category].append(
                {
                    "class_name": class_name,
                    "file_path": str(file_path.relative_to(source_root)),
                    "methods": methods,
                    "request_mappings": request_mappings,
                    "annotations": class_annotations or self._extract_annotations(text),
                    "fields": fields,
                    "method_details": method_details,
                }
            )

        artifact_path = artifact_dir / "03-component-inventory.md"
        artifact_path.write_text(self._render_markdown(components), encoding="utf-8")
        return ComponentDiscoveryResult(components=components, artifact_path=artifact_path)

    def _classify_component(self, file_path: Path, text: str) -> str | None:
        lowered_path = str(file_path).lower()
        lowered_text = text.lower()

        for category, markers in self.CATEGORY_RULES.items():
            for marker in markers:
                if marker.startswith("@") and marker in text:
                    return category
                if marker.lower() in lowered_path or marker.lower() in lowered_text:
                    if category == "dtos" and "dto" not in lowered_path:
                        continue
                    return category
        return None

    def _extract_class_name(self, text: str) -> str | None:
        match = self.CLASS_PATTERN.search(text)
        return match.group(1) if match else None

    def _extract_methods(self, text: str) -> list[str]:
        return [match.group(2) for match in self.METHOD_PATTERN.finditer(text)]

    def _extract_structure(self, text: str) -> tuple[list[str], list[dict[str, object]], list[dict[str, object]]]:
        class_annotations: list[str] = []
        fields: list[dict[str, object]] = []
        methods: list[dict[str, object]] = []
        pending_annotations: list[str] = []

        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("//"):
                continue

            if line.startswith("@"):
                pending_annotations.append(line)
                continue

            if " class " in f" {line} " and "class " in line:
                class_annotations = [annotation.split("(")[0] for annotation in pending_annotations]
                pending_annotations = []
                continue

            field_match = self.FIELD_PATTERN.match(line)
            if field_match and "(" not in line:
                fields.append(
                    {
                        "name": field_match.group(3),
                        "type": field_match.group(2),
                        "annotations": [annotation.split("(")[0] for annotation in pending_annotations],
                    }
                )
                pending_annotations = []
                continue

            method_match = self.METHOD_SIGNATURE_PATTERN.match(line)
            if method_match:
                methods.append(
                    {
                        "name": method_match.group(3),
                        "return_type": " ".join(method_match.group(2).split()),
                        "parameters": self._extract_parameters(method_match.group(4)),
                        "annotations": [annotation.split("(")[0] for annotation in pending_annotations],
                        "mapping_annotations": [
                            annotation
                            for annotation in pending_annotations
                            if any(
                                marker in annotation
                                for marker in (
                                    "@RequestMapping",
                                    "@GetMapping",
                                    "@PostMapping",
                                    "@PutMapping",
                                    "@DeleteMapping",
                                    "@PatchMapping",
                                )
                            )
                        ],
                    }
                )
                pending_annotations = []
                continue

            pending_annotations = []

        return class_annotations, fields, methods

    def _extract_parameters(self, parameters_text: str) -> list[dict[str, object]]:
        if not parameters_text.strip():
            return []

        parameters: list[dict[str, object]] = []
        for raw_parameter in self._split_parameters(parameters_text):
            parameter = raw_parameter.strip()
            if not parameter:
                continue
            annotations = re.findall(r"(@[A-Za-z0-9_]+(?:\([^)]*\))?)", parameter)
            parameter_without_annotations = re.sub(r"@[A-Za-z0-9_]+(?:\([^)]*\))?\s*", "", parameter).strip()
            tokens = parameter_without_annotations.split()
            if len(tokens) < 2:
                continue
            name = tokens[-1]
            type_name = " ".join(tokens[:-1])
            parameters.append(
                {
                    "name": name,
                    "type": type_name,
                    "annotations": annotations,
                }
            )
        return parameters

    def _split_parameters(self, text: str) -> list[str]:
        parameters: list[str] = []
        current: list[str] = []
        depth = 0
        for char in text:
            if char == "<":
                depth += 1
            elif char == ">" and depth > 0:
                depth -= 1
            elif char == "," and depth == 0:
                parameters.append("".join(current))
                current = []
                continue
            current.append(char)
        if current:
            parameters.append("".join(current))
        return parameters

    def _extract_request_mappings(self, text: str) -> list[str]:
        mappings: list[str] = []
        for match in self.REQUEST_MAPPING_PATTERN.finditer(text):
            mappings.append(match.group(0))
        return mappings

    def _extract_annotations(self, text: str) -> list[str]:
        annotations: list[str] = []
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("@"):
                annotations.append(stripped.split("(")[0])
        return annotations[:20]

    def _render_markdown(self, components: dict[str, list[dict[str, object]]]) -> str:
        lines = ["# Component Inventory", ""]
        for category, items in components.items():
            lines.append(f"## {category.replace('_', ' ').title()}")
            if not items:
                lines.append("- none")
                lines.append("")
                continue
            for item in items:
                lines.append(f"- {item['class_name']} ({item['file_path']})")
                methods = item.get("methods") or []
                if methods:
                    lines.append(f"  methods: {', '.join(methods[:8])}")
                mappings = item.get("request_mappings") or []
                if mappings:
                    lines.append(f"  mappings: {' | '.join(mappings[:5])}")
                fields = item.get("fields") or []
                if fields:
                    field_text = ", ".join(f"{field['name']}:{field['type']}" for field in fields[:8])
                    lines.append(f"  fields: {field_text}")
            lines.append("")
        return "\n".join(lines) + "\n"
