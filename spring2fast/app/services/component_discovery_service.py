"""Generic Spring Boot component discovery."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.llm import get_analysis_model


@dataclass(slots=True)
class ComponentDiscoveryResult:
    """Structured output for discovered Spring Boot components."""

    components: dict[str, list[dict[str, object]]]
    artifact_path: Path


class ComponentDiscoveryService:
    """Discovers Spring Boot component categories from Java source files."""

    CLASS_PATTERN = re.compile(
        r"^(?:public\s+)?(?:abstract\s+)?(?:final\s+)?class\s+([A-Z][A-Za-z0-9_]+)",
        re.MULTILINE,
    )
    METHOD_SIGNATURE_PATTERN = re.compile(
        r"(public|private|protected)\s+([A-Za-z0-9_<>,\[\]\s?]+?)\s+([A-Za-z0-9_]+)\s*\((.*?)\)\s*(?:\{|throws|$)",
    )
    FIELD_PATTERN = re.compile(
        r"(private|protected|public)\s+(?!class\b|interface\b|enum\b)(?:final\s+)?([A-Za-z0-9_<>,\[\]\.?]+)\s+([A-Za-z0-9_]+)\s*(?:=\s*[^;]+)?;",
    )
    REQUEST_MAPPING_PATTERN = re.compile(r'@(?:RequestMapping|GetMapping|PostMapping|PutMapping|DeleteMapping|PatchMapping)\s*\((.*?)\)')
    EXTENDS_PATTERN = re.compile(r"(?:class|interface)\s+[A-Za-z0-9_]+\s+extends\s+([A-Za-z0-9_]+)")
    JPQL_QUERY_PATTERN = re.compile(r'@Query\s*\((.*?)\)', re.DOTALL)

    CATEGORY_RULES = {
        "exception_handlers": ["@ControllerAdvice", "@RestControllerAdvice"],
        "controllers": ["@RestController", "@Controller"],
        "services": ["@Service"],
        "repositories": ["@Repository"],
        "entities": ["@Entity"],
        "enums": [],
        "dtos": ["dto"],
        "security": ["SecurityFilterChain", "@EnableWebSecurity", "WebSecurityConfigurerAdapter"],
        "configs": ["@Configuration"],
        "feign_clients": ["@FeignClient"],
        "event_handlers": ["@KafkaListener", "@RabbitListener", "@EventListener"],
        "cache_components": ["@Cacheable", "@CachePut", "@CacheEvict"],
        "scheduled_tasks": ["@Scheduled"],
        "embeddables": ["@Embeddable"],
    }

    JPA_REPO_BASES = (
        "JpaRepository", "CrudRepository",
        "PagingAndSortingRepository", "Repository",
        "MongoRepository", "ReactiveCrudRepository",
    )

    def discover(self, *, input_dir: str, artifacts_dir: str) -> ComponentDiscoveryResult:
        """Discover Spring Boot components and write a normalized artifact."""
        source_root = Path(input_dir)
        artifact_dir = Path(artifacts_dir)
        artifact_dir.mkdir(parents=True, exist_ok=True)

        components: dict[str, list[dict[str, object]]] = {key: [] for key in self.CATEGORY_RULES}
        components["mapped_superclasses"] = []

        class_registry: dict[str, dict[str, object]] = {}
        for file_path in source_root.rglob("*.java"):
            if ".git" in file_path.parts:
                continue
            parts_lower = [p.lower() for p in file_path.parts]
            if "test" in parts_lower or file_path.stem.lower().endswith(("test", "tests")):
                continue

            text = file_path.read_text(encoding="utf-8", errors="ignore")
            class_name = self._extract_class_name(text) or file_path.stem
            class_registry[class_name] = {
                "class_name": class_name,
                "file_path": str(file_path.relative_to(source_root)),
                "text": text,
                "extends": self._extract_extends(text),
                "is_mapped_superclass": "@MappedSuperclass" in text,
            }

        unclassified: list[dict[str, object]] = []
        service_names = {
            str(class_name)
            for class_name, registry_item in class_registry.items()
            if self._classify_component(
                source_root / str(registry_item["file_path"]),
                str(registry_item["text"]),
            ) == "services"
        }

        for item in class_registry.values():
            text = str(item["text"])
            file_path = source_root / str(item["file_path"])
            category = self._classify_component(file_path, text)
            if category is None:
                unclassified.append(
                    {
                        "class_name": item["class_name"],
                        "file_path": item["file_path"],
                        "source": text,
                    }
                )

            class_annotations, fields, method_details = self._extract_structure(text)
            request_mappings = self._extract_request_mappings(text)
            query_methods = self._extract_query_methods(method_details)
            inherited_fields, superclass_chain = self._resolve_superclass_fields(
                class_registry=class_registry,
                class_name=str(item["class_name"]),
            )

            component_payload = {
                "class_name": item["class_name"],
                "file_path": item["file_path"],
                "methods": [detail["name"] for detail in method_details],
                "request_mappings": request_mappings,
                "annotations": class_annotations or self._extract_annotations(text),
                "fields": fields,
                "inherited_fields": inherited_fields,
                "all_fields": [*inherited_fields, *fields],
                "superclass_chain": superclass_chain,
                "extends": item["extends"],
                "method_details": method_details,
                "query_methods": query_methods,
                "bean_validation_summary": self._build_validation_summary([*inherited_fields, *fields]),
                "table_name": self._extract_table_name(text) if category == "entities" else None,
                "inheritance_strategy": self._extract_inheritance_strategy(text) if category == "entities" else None,
                "enum_values": self._extract_enum_values(text) if category == "enums" else [],
            }

            if category == "controllers":
                component_payload["dependencies"] = self._extract_injected_dependencies(text)
                component_payload["service_calls"] = self._extract_service_method_calls(
                    text,
                    service_names,
                )

            if bool(item["is_mapped_superclass"]):
                components["mapped_superclasses"].append(component_payload)

            if category:
                components[category].append(component_payload)

        enriched_components = LLMComponentEnricher(self).enrich_unclassified(
            unclassified=unclassified,
            inventory=components,
        )
        for category, items in enriched_components.items():
            components.setdefault(category, []).extend(items)

        artifact_path = artifact_dir / "03-component-inventory.md"
        artifact_path.write_text(self._render_markdown(components), encoding="utf-8")

        # ── Write ground truth JSON for CDA scoring ──
        import json as _json
        ground_truth = {
            "entities": [str(c["class_name"]) for c in components.get("entities", [])],
            "services": [str(c["class_name"]) for c in components.get("services", [])],
            "repositories": [str(c["class_name"]) for c in components.get("repositories", [])],
            "controllers": [str(c["class_name"]) for c in components.get("controllers", [])],
            "dtos": [str(c["class_name"]) for c in components.get("dtos", [])],
            "exception_handlers": [str(c["class_name"]) for c in components.get("exception_handlers", [])],
            "feign_clients": [str(c["class_name"]) for c in components.get("feign_clients", [])],
            "event_handlers": [str(c["class_name"]) for c in components.get("event_handlers", [])],
            "scheduled_tasks": [str(c["class_name"]) for c in components.get("scheduled_tasks", [])],
            "total_expected_methods": sum(
                len(c.get("methods") or [])
                for cat_list in components.values()
                for c in cat_list
            ),
            "expected_classes": sum(len(v) for v in components.values()),
        }
        ground_truth_path = artifact_dir / "ground_truth.json"
        ground_truth_path.write_text(_json.dumps(ground_truth, indent=2), encoding="utf-8")

        return ComponentDiscoveryResult(components=components, artifact_path=artifact_path)

    def _classify_component(self, file_path: Path, text: str) -> str | None:
        lowered_path = str(file_path).lower()
        lowered_text = text.lower()
        annotations = set(self._extract_annotations(text))

        if re.search(r"\benum\s+[A-Z]\w+\s*\{", text):
            return "enums"

        if "interface " in text:
            for base in self.JPA_REPO_BASES:
                if f"extends {base}" in text or f"extends {base}<" in text:
                    return "repositories"

        for category, markers in self.CATEGORY_RULES.items():
            for marker in markers:
                if marker.startswith("@") and marker in annotations:
                    return category
                if marker.lower() in lowered_path or marker.lower() in lowered_text:
                    if category == "dtos" and "dto" not in lowered_path:
                        continue
                    return category
        return None

    def _extract_class_name(self, text: str) -> str | None:
        match = self.CLASS_PATTERN.search(text)
        return match.group(1) if match else None

    def _extract_extends(self, text: str) -> str | None:
        match = self.EXTENDS_PATTERN.search(text)
        return match.group(1) if match else None

    def _extract_table_name(self, text: str) -> str | None:
        match = re.search(r'@Table\s*\(\s*name\s*=\s*"([^"]+)"', text)
        return match.group(1) if match else None

    def _extract_inheritance_strategy(self, text: str) -> str | None:
        match = re.search(
            r"@Inheritance\s*\(\s*strategy\s*=\s*InheritanceType\.(\w+)",
            text,
        )
        return match.group(1) if match else None

    def _extract_enum_values(self, text: str) -> list[str]:
        values: list[str] = []
        enum_body = re.search(r"enum\s+\w+[^{]*\{([^}]+)", text, re.DOTALL)
        if not enum_body:
            return values

        body = enum_body.group(1).split(";", 1)[0]
        for part in body.split(","):
            candidate = part.strip()
            if not candidate:
                continue
            match = re.match(r"([A-Z_0-9]+)", candidate)
            if match:
                values.append(match.group(1))
        return values

    def _extract_injected_dependencies(self, text: str) -> list[dict[str, str]]:
        deps: list[dict[str, str]] = []
        for field in self.FIELD_PATTERN.finditer(text):
            field_type = field.group(2).strip()
            field_name = field.group(3).strip()
            if field_type and field_type[0].isupper() and field_type not in {
                "String", "Long", "Integer", "Boolean", "List", "Map", "Set",
            }:
                deps.append({"name": field_name, "type": field_type})
        return deps

    def _extract_service_method_calls(self, text: str, service_names: set[str]) -> list[str]:
        calls: set[str] = set()
        for svc_name in service_names:
            if not svc_name:
                continue
            var_name = svc_name[0].lower() + svc_name[1:]
            pattern = re.compile(rf"\b{re.escape(var_name)}\.(\w+)\s*\(")
            for match in pattern.finditer(text):
                calls.add(match.group(1))
        return sorted(calls)

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
                annotations = [annotation.split("(")[0] for annotation in pending_annotations]
                fields.append(
                    {
                        "name": field_match.group(3),
                        "type": field_match.group(2),
                        "annotations": annotations,
                        "validation": self._parse_validation_annotations(pending_annotations),
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
                        "raw_annotations": list(pending_annotations),
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
                        "query": self._extract_query_annotation(pending_annotations),
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
        return [match.group(0) for match in self.REQUEST_MAPPING_PATTERN.finditer(text)]

    def _extract_annotations(self, text: str) -> list[str]:
        annotations: list[str] = []
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("@"):
                annotations.append(stripped.split("(")[0])
        return annotations[:20]

    def _extract_query_annotation(self, annotations: list[str]) -> str | None:
        for annotation in annotations:
            if annotation.startswith("@Query"):
                return annotation
        return None

    def _extract_query_methods(self, method_details: list[dict[str, object]]) -> list[dict[str, object]]:
        query_methods: list[dict[str, object]] = []
        for method in method_details:
            method_name = str(method["name"])
            if method_name.startswith(("findBy", "existsBy", "countBy", "deleteBy")) or method.get("query"):
                query_methods.append(
                    {
                        "name": method_name,
                        "query": method.get("query"),
                        "parameters": method.get("parameters", []),
                        "return_type": method.get("return_type"),
                    }
                )
        return query_methods

    def _resolve_superclass_fields(
        self,
        *,
        class_registry: dict[str, dict[str, object]],
        class_name: str,
    ) -> tuple[list[dict[str, object]], list[str]]:
        chain: list[str] = []
        parent_names: list[str] = []
        visited: set[str] = set()
        current = class_registry.get(class_name, {}).get("extends")
        while current and current not in visited:
            visited.add(str(current))
            parent = class_registry.get(str(current))
            if not parent:
                break
            parent_names.append(str(current))
            current = parent.get("extends")

        chain = list(reversed(parent_names))
        inherited_fields: list[dict[str, object]] = []
        seen_field_names: set[str] = set()
        for parent_name in chain:
            parent = class_registry.get(parent_name)
            if not parent:
                continue
            _, parent_fields, _ = self._extract_structure(str(parent["text"]))
            for field in parent_fields:
                field_name = str(field["name"])
                if field_name not in seen_field_names:
                    inherited_fields.append(field)
                    seen_field_names.add(field_name)

        return inherited_fields, chain

    def _parse_validation_annotations(self, annotations: list[str]) -> dict[str, object]:
        summary: dict[str, object] = {}
        for annotation in annotations:
            name = annotation.split("(")[0]
            if name in {"@NotNull", "@NotBlank", "@NotEmpty"}:
                summary["required"] = True
            if name == "@Email":
                summary["format"] = "email"
            if name == "@Pattern":
                pattern = re.search(r'regexp\s*=\s*"([^"]+)"', annotation)
                if pattern:
                    summary["pattern"] = pattern.group(1)
            if name == "@Size":
                min_match = re.search(r"min\s*=\s*(\d+)", annotation)
                max_match = re.search(r"max\s*=\s*(\d+)", annotation)
                if min_match:
                    summary["min_length"] = int(min_match.group(1))
                if max_match:
                    summary["max_length"] = int(max_match.group(1))
            if name == "@Min":
                min_match = re.search(r"\((\d+)\)", annotation)
                if min_match:
                    summary["ge"] = int(min_match.group(1))
            if name == "@Max":
                max_match = re.search(r"\((\d+)\)", annotation)
                if max_match:
                    summary["le"] = int(max_match.group(1))
        return summary

    def _build_validation_summary(self, fields: list[dict[str, object]]) -> list[str]:
        lines: list[str] = []
        for field in fields:
            validation = field.get("validation") or {}
            if validation:
                lines.append(f"{field['name']}: {validation}")
        return lines

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
                inherited_fields = item.get("inherited_fields") or []
                if inherited_fields:
                    inherited_text = ", ".join(f"{field['name']}:{field['type']}" for field in inherited_fields[:8])
                    lines.append(f"  inherited_fields: {inherited_text}")
                methods = item.get("methods") or []
                if methods:
                    lines.append(f"  methods: {', '.join(methods[:8])}")
                mappings = item.get("request_mappings") or []
                if mappings:
                    lines.append(f"  mappings: {' | '.join(mappings[:5])}")
                fields = item.get("all_fields") or item.get("fields") or []
                if fields:
                    field_text = ", ".join(f"{field['name']}:{field['type']}" for field in fields[:8])
                    lines.append(f"  fields: {field_text}")
                if item.get("table_name"):
                    lines.append(f"  table_name: {item['table_name']}")
                if item.get("inheritance_strategy"):
                    lines.append(f"  inheritance_strategy: {item['inheritance_strategy']}")
                enum_values = item.get("enum_values") or []
                if enum_values:
                    lines.append(f"  enum_values: {', '.join(enum_values[:12])}")
                dependencies = item.get("dependencies") or []
                if dependencies:
                    dep_text = ", ".join(f"{dep['name']}:{dep['type']}" for dep in dependencies[:8])
                    lines.append(f"  dependencies: {dep_text}")
                service_calls = item.get("service_calls") or []
                if service_calls:
                    lines.append(f"  service_calls: {', '.join(service_calls[:8])}")
                validations = item.get("bean_validation_summary") or []
                if validations:
                    lines.append(f"  validations: {' | '.join(validations[:5])}")
            lines.append("")
        return "\n".join(lines) + "\n"


class LLMComponentEnricher:
    """Use an LLM to classify Java files that regex could not categorize."""

    ROLE_TO_CATEGORY = {
        "entity": "entities",
        "dto": "dtos",
        "service": "services",
        "repository": "repositories",
        "controller": "controllers",
        "config": "configs",
    }

    CLASSIFICATION_PROMPT = (
        "You are analyzing Java Spring Boot source files.\n"
        "For each file, determine its role. Options:\n"
        "  entity - domain object / DB model\n"
        "  dto - request/response transfer object\n"
        "  service - business logic class\n"
        "  repository - data access layer\n"
        "  controller - HTTP endpoint handler\n"
        "  config - application configuration\n"
        "  utility - helper/util, skip it\n"
        "  unknown - truly unclear\n"
        'Return ONLY JSON: {"filename": "role", ...}'
    )

    def __init__(self, service: ComponentDiscoveryService, model=None) -> None:
        self.service = service
        self.model = model or get_analysis_model()

    @property
    def enabled(self) -> bool:
        return self.model is not None

    def enrich_unclassified(
        self,
        *,
        unclassified: list[dict[str, object]],
        inventory: dict[str, list[dict[str, object]]],
    ) -> dict[str, list[dict[str, object]]]:
        if not self.enabled or not unclassified:
            return {}

        candidates = unclassified[:25]
        files_block = "\n\n".join(
            f"### {item['file_path']}\n{str(item['source'])[:600]}"
            for item in candidates
        )
        try:
            response = self.model.invoke([
                SystemMessage(content=self.CLASSIFICATION_PROMPT),
                HumanMessage(content=f"Files to classify:\n{files_block}"),
            ])
        except Exception:
            return {}

        content = response.content if isinstance(response.content, str) else str(response.content)
        mapping = self._parse_response(content)
        existing_keys = {
            (category, str(component.get("class_name")))
            for category, items in inventory.items()
            for component in items
        }

        enriched: dict[str, list[dict[str, object]]] = {}
        for item in candidates:
            role = mapping.get(str(item["file_path"]))
            category = self.ROLE_TO_CATEGORY.get(role or "")
            if not category:
                continue
            key = (category, str(item["class_name"]))
            if key in existing_keys:
                continue

            source = str(item["source"])
            class_annotations, fields, method_details = self.service._extract_structure(source)
            payload = {
                "class_name": item["class_name"],
                "file_path": item["file_path"],
                "methods": [detail["name"] for detail in method_details],
                "request_mappings": self.service._extract_request_mappings(source),
                "annotations": class_annotations or self.service._extract_annotations(source),
                "fields": fields,
                "inherited_fields": [],
                "all_fields": fields,
                "superclass_chain": [],
                "extends": self.service._extract_extends(source),
                "method_details": method_details,
                "query_methods": self.service._extract_query_methods(method_details),
                "bean_validation_summary": self.service._build_validation_summary(fields),
                "table_name": self.service._extract_table_name(source) if category == "entities" else None,
                "inheritance_strategy": (
                    self.service._extract_inheritance_strategy(source)
                    if category == "entities" else None
                ),
                "enum_values": [],
            }
            enriched.setdefault(category, []).append(payload)

        return enriched

    @staticmethod
    def _parse_response(content: str) -> dict[str, str]:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = "\n".join(
                line for line in cleaned.splitlines() if not line.startswith("```")
            ).strip()
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            return {}
        return {
            str(key): str(value).strip().lower()
            for key, value in parsed.items()
            if isinstance(key, str) and isinstance(value, str)
        }
