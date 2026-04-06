"""Deterministic Java source parser using the javalang AST library.

Falls back gracefully to regex extraction when javalang cannot parse
(e.g. Java 17+ syntax like records, sealed classes, text blocks).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Intermediate Representation (IR) dataclasses
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class FieldIR:
    name: str
    type: str
    annotations: list[dict[str, Any]] = field(default_factory=list)
    modifiers: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ParameterIR:
    name: str
    type: str
    annotations: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class MethodIR:
    name: str
    return_type: str = "void"
    parameters: list[ParameterIR] = field(default_factory=list)
    annotations: list[dict[str, Any]] = field(default_factory=list)
    modifiers: list[str] = field(default_factory=list)
    body_line_count: int = 0
    body_source: str = ""


@dataclass(slots=True)
class ClassIR:
    name: str
    kind: str = "class"  # class | interface | enum
    package: str | None = None
    annotations: list[dict[str, Any]] = field(default_factory=list)
    extends: str | None = None
    implements: list[str] = field(default_factory=list)
    fields: list[FieldIR] = field(default_factory=list)
    methods: list[MethodIR] = field(default_factory=list)
    constructors: list[MethodIR] = field(default_factory=list)


@dataclass(slots=True)
class JavaFileIR:
    """Full parse result for a single .java file."""
    file_path: str = ""
    package: str | None = None
    imports: list[str] = field(default_factory=list)
    classes: list[ClassIR] = field(default_factory=list)
    parse_method: str = "none"  # "javalang" | "regex" | "none"


# ---------------------------------------------------------------------------
# Parser implementation
# ---------------------------------------------------------------------------

class JavaASTParser:
    """Wraps javalang for AST parsing with regex fallback."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse_file(self, source: str, *, file_path: str = "") -> JavaFileIR:
        """Parse a Java source string into a structured IR.

        Attempts javalang first; on failure falls back to regex extraction.
        """
        try:
            return self._parse_with_javalang(source, file_path=file_path)
        except Exception:
            return self._parse_with_regex(source, file_path=file_path)

    def extract_method_bodies(self, source: str) -> dict[str, str]:
        """Return ``{method_name: raw_java_body}`` for every method in *source*.

        Uses a brace-counting heuristic on the raw text to slice bodies,
        since javalang does not preserve raw source offsets reliably.
        """
        bodies: dict[str, str] = {}
        # Match method signatures followed by "{"
        pattern = re.compile(
            r'(?:public|protected|private|static|final|abstract|synchronized|native|\s)*'
            r'(?:<[^>]+>\s+)?'                # generic return type
            r'[\w<>\[\],\s]+\s+'              # return type
            r'(\w+)'                          # method name
            r'\s*\([^)]*\)'                   # parameters
            r'(?:\s*throws\s+[\w,.\s]+)?'     # throws clause
            r'\s*\{',                          # opening brace
            re.MULTILINE,
        )
        for match in pattern.finditer(source):
            method_name = match.group(1)
            brace_start = match.end() - 1  # position of "{"
            body_end = self._find_matching_brace(source, brace_start)
            if body_end > brace_start:
                body = source[brace_start + 1 : body_end].strip()
                bodies[method_name] = body
        return bodies

    # ------------------------------------------------------------------
    # javalang-based parsing
    # ------------------------------------------------------------------

    def _parse_with_javalang(self, source: str, *, file_path: str) -> JavaFileIR:
        import javalang  # type: ignore[import-untyped]

        tree = javalang.parse.parse(source)
        method_bodies = self.extract_method_bodies(source)

        classes: list[ClassIR] = []
        for _, cls in tree.filter(javalang.tree.ClassDeclaration):
            classes.append(self._jl_class(cls, "class", method_bodies))
        for _, iface in tree.filter(javalang.tree.InterfaceDeclaration):
            classes.append(self._jl_class(iface, "interface", method_bodies))
        for _, enum in tree.filter(javalang.tree.EnumDeclaration):
            classes.append(self._jl_class(enum, "enum", method_bodies))

        pkg = tree.package.name if tree.package else None
        for c in classes:
            c.package = pkg

        return JavaFileIR(
            file_path=file_path,
            package=pkg,
            imports=[imp.path for imp in tree.imports],
            classes=classes,
            parse_method="javalang",
        )

    def _jl_class(self, node: Any, kind: str, method_bodies: dict[str, str]) -> ClassIR:
        extends = None
        if hasattr(node, "extends") and node.extends:
            extends = node.extends.name if hasattr(node.extends, "name") else str(node.extends)

        implements: list[str] = []
        if hasattr(node, "implements") and node.implements:
            implements = [impl.name for impl in node.implements]

        fields = [self._jl_field(f) for f in (node.fields or [])]
        methods = [self._jl_method(m, method_bodies) for m in (node.methods or [])]
        constructors = [self._jl_method(c, method_bodies) for c in (node.constructors or [])] if hasattr(node, "constructors") else []

        return ClassIR(
            name=node.name,
            kind=kind,
            annotations=[self._jl_annotation(a) for a in (node.annotations or [])],
            extends=extends,
            implements=implements,
            fields=fields,
            methods=methods,
            constructors=constructors,
        )

    def _jl_field(self, field_node: Any) -> FieldIR:
        name = field_node.declarators[0].name if field_node.declarators else "unknown"
        return FieldIR(
            name=name,
            type=self._jl_type_to_string(field_node.type),
            annotations=[self._jl_annotation(a) for a in (field_node.annotations or [])],
            modifiers=list(field_node.modifiers or []),
        )

    def _jl_method(self, method_node: Any, method_bodies: dict[str, str]) -> MethodIR:
        ret_type = "void"
        if hasattr(method_node, "return_type") and method_node.return_type:
            ret_type = self._jl_type_to_string(method_node.return_type)

        params = [
            ParameterIR(
                name=p.name,
                type=self._jl_type_to_string(p.type),
                annotations=[self._jl_annotation(a) for a in (p.annotations or [])],
            )
            for p in (method_node.parameters or [])
        ]

        return MethodIR(
            name=method_node.name,
            return_type=ret_type,
            parameters=params,
            annotations=[self._jl_annotation(a) for a in (method_node.annotations or [])],
            modifiers=list(method_node.modifiers or []),
            body_line_count=len(method_node.body) if method_node.body else 0,
            body_source=method_bodies.get(method_node.name, ""),
        )

    def _jl_annotation(self, ann: Any) -> dict[str, Any]:
        args: dict[str, str] = {}
        if ann.element:
            if isinstance(ann.element, list):
                for elem in ann.element:
                    if hasattr(elem, "name") and hasattr(elem, "value"):
                        args[elem.name] = self._jl_element_value(elem.value)
            else:
                # Single-value annotation like @RequestMapping("/path")
                args["value"] = self._jl_element_value(ann.element)
        return {"name": ann.name, "arguments": args}

    def _jl_element_value(self, val: Any) -> str:
        if hasattr(val, "value"):
            return str(val.value)
        if isinstance(val, list):
            return str([self._jl_element_value(v) for v in val])
        return str(val)

    def _jl_type_to_string(self, type_node: Any) -> str:
        if type_node is None:
            return "void"
        name = type_node.name
        if hasattr(type_node, "arguments") and type_node.arguments:
            args = ", ".join(
                self._jl_type_to_string(a.type) if hasattr(a, "type") and a.type else (a.name if hasattr(a, "name") else "?")
                for a in type_node.arguments
            )
            return f"{name}<{args}>"
        if hasattr(type_node, "dimensions") and type_node.dimensions:
            return f"{name}[]"
        return name

    # ------------------------------------------------------------------
    # Regex fallback parser
    # ------------------------------------------------------------------

    def _parse_with_regex(self, source: str, *, file_path: str) -> JavaFileIR:
        method_bodies = self.extract_method_bodies(source)

        pkg_match = re.search(r"package\s+([\w.]+)\s*;", source)
        package = pkg_match.group(1) if pkg_match else None

        imports = re.findall(r"import\s+(?:static\s+)?([\w.*]+)\s*;", source)

        classes: list[ClassIR] = []
        class_pattern = re.compile(
            r"(?:@\w+(?:\([^)]*\))?[\s\n]*)+"
            r"(?:public\s+|protected\s+|private\s+|abstract\s+|final\s+)*"
            r"(class|interface|enum)\s+"
            r"(\w+)"
            r"(?:\s+extends\s+(\w+))?"
            r"(?:\s+implements\s+([\w,\s]+))?",
            re.MULTILINE,
        )

        for m in class_pattern.finditer(source):
            kind = m.group(1)
            name = m.group(2)
            extends = m.group(3)
            implements = [s.strip() for s in m.group(4).split(",")] if m.group(4) else []

            # Extract annotations above the class declaration
            annotations = self._regex_extract_annotations(source[: m.start()])

            # Extract fields
            fields = self._regex_extract_fields(source)

            # Extract methods
            methods = self._regex_extract_methods(source, method_bodies)

            classes.append(ClassIR(
                name=name,
                kind=kind,
                package=package,
                annotations=annotations,
                extends=extends,
                implements=implements,
                fields=fields,
                methods=methods,
            ))

        return JavaFileIR(
            file_path=file_path,
            package=package,
            imports=imports,
            classes=classes,
            parse_method="regex",
        )

    def _regex_extract_annotations(self, preceding_text: str) -> list[dict[str, Any]]:
        """Extract annotations from a block of text."""
        ann_pattern = re.compile(r"@(\w+)(?:\(([^)]*)\))?")
        result: list[dict[str, Any]] = []
        # Only look at the last few lines before the class
        lines = preceding_text.strip().split("\n")
        ann_block = "\n".join(lines[-10:]) if len(lines) > 10 else preceding_text
        for m in ann_pattern.finditer(ann_block):
            args: dict[str, str] = {}
            if m.group(2):
                args["value"] = m.group(2).strip().strip("\"'")
            result.append({"name": m.group(1), "arguments": args})
        return result

    def _regex_extract_fields(self, source: str) -> list[FieldIR]:
        """Extract fields declared as `private Type name;` etc."""
        field_pattern = re.compile(
            r"(?:(@\w+(?:\([^)]*\))?)\s+)*"
            r"(?:private|protected|public)\s+"
            r"(?:static\s+)?(?:final\s+)?"
            r"([\w<>\[\],\s]+?)\s+"
            r"(\w+)\s*[;=]",
        )
        fields: list[FieldIR] = []
        for m in field_pattern.finditer(source):
            annotations: list[dict[str, Any]] = []
            if m.group(1):
                ann_m = re.match(r"@(\w+)(?:\(([^)]*)\))?", m.group(1))
                if ann_m:
                    annotations.append({
                        "name": ann_m.group(1),
                        "arguments": {"value": ann_m.group(2)} if ann_m.group(2) else {},
                    })
            fields.append(FieldIR(
                name=m.group(3),
                type=m.group(2).strip(),
                annotations=annotations,
            ))
        return fields

    def _regex_extract_methods(self, source: str, method_bodies: dict[str, str]) -> list[MethodIR]:
        """Extract methods from Java source via regex."""
        method_pattern = re.compile(
            r"(?:(?:@\w+(?:\([^)]*\))?)\s+)*"
            r"(?:public|protected|private|static|final|abstract|synchronized|\s)*"
            r"(?:<[^>]+>\s+)?"
            r"([\w<>\[\],]+)\s+"   # return type
            r"(\w+)"              # method name
            r"\s*\(([^)]*)\)"     # params
            r"(?:\s*throws\s+[\w,.\s]+)?"
            r"\s*\{",
            re.MULTILINE,
        )
        methods: list[MethodIR] = []
        for m in method_pattern.finditer(source):
            ret_type = m.group(1)
            name = m.group(2)
            raw_params = m.group(3).strip()
            params = self._regex_parse_params(raw_params) if raw_params else []
            body = method_bodies.get(name, "")
            methods.append(MethodIR(
                name=name,
                return_type=ret_type,
                parameters=params,
                body_line_count=body.count("\n") + 1 if body else 0,
                body_source=body,
            ))
        return methods

    def _regex_parse_params(self, raw: str) -> list[ParameterIR]:
        """Parse raw parameter text like ``@RequestBody UserDto user, @PathVariable Long id``."""
        params: list[ParameterIR] = []
        parts = self._split_params(raw)
        for part in parts:
            part = part.strip()
            if not part:
                continue
            # Extract annotations
            anns: list[dict[str, Any]] = []
            while part.startswith("@"):
                ann_m = re.match(r"@(\w+)(?:\(([^)]*)\))?\s*", part)
                if ann_m:
                    anns.append({
                        "name": ann_m.group(1),
                        "arguments": {"value": ann_m.group(2)} if ann_m.group(2) else {},
                    })
                    part = part[ann_m.end():].strip()
                else:
                    break
            # Remaining should be "Type name" or "Type<Generic> name"
            tokens = part.rsplit(None, 1)
            if len(tokens) == 2:
                params.append(ParameterIR(name=tokens[1], type=tokens[0], annotations=anns))
            elif len(tokens) == 1:
                params.append(ParameterIR(name=tokens[0], type="Object", annotations=anns))
        return params

    @staticmethod
    def _split_params(raw: str) -> list[str]:
        """Split parameter text on commas, respecting generics angle brackets."""
        parts: list[str] = []
        depth = 0
        current: list[str] = []
        for ch in raw:
            if ch == "<":
                depth += 1
            elif ch == ">":
                depth -= 1
            elif ch == "," and depth == 0:
                parts.append("".join(current))
                current = []
                continue
            current.append(ch)
        if current:
            parts.append("".join(current))
        return parts

    @staticmethod
    def _find_matching_brace(source: str, start: int) -> int:
        """Return index of the closing ``}`` matching the ``{`` at *start*."""
        depth = 0
        in_string = False
        escape = False
        quote_char = ""
        for i in range(start, len(source)):
            ch = source[i]
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if in_string:
                if ch == quote_char:
                    in_string = False
                continue
            if ch in ('"', "'"):
                in_string = True
                quote_char = ch
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return i
        return start
