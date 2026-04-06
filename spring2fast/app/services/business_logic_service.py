"""Business logic extraction from Java source files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from app.services.business_logic_llm_enricher import BusinessLogicLLMEnricher


@dataclass(slots=True)
class BusinessLogicResult:
    """Structured output from business logic extraction."""

    rules: list[str]
    classes_analyzed: list[str]
    artifact_path: Path
    llm_summary: str | None


class BusinessLogicService:
    """Extract business-rule hints from Java services and controllers."""

    CLASS_PATTERN = re.compile(r"class\s+([A-Za-z0-9_]+)")
    METHOD_PATTERN = re.compile(
        r"(public|private|protected)\s+[A-Za-z0-9_<>,\[\]\s]+\s+([A-Za-z0-9_]+)\s*\(",
    )
    CONDITION_PATTERN = re.compile(r"\bif\s*\((.+?)\)")
    THROW_PATTERN = re.compile(r"throw\s+new\s+([A-Za-z0-9_]+)\s*\((.*?)\)")

    def __init__(self, enricher: BusinessLogicLLMEnricher | None = None) -> None:
        self.enricher = enricher or BusinessLogicLLMEnricher()

    def extract(self, *, input_dir: str, artifacts_dir: str) -> BusinessLogicResult:
        """Extract business rules and write a markdown artifact."""
        source_root = Path(input_dir)
        artifact_dir = Path(artifacts_dir)
        artifact_dir.mkdir(parents=True, exist_ok=True)

        java_files = [path for path in source_root.rglob("*.java") if ".git" not in path.parts]
        interesting_files = [path for path in java_files if self._is_business_logic_file(path)]
        if not interesting_files:
            interesting_files = java_files[:8]

        rules: list[str] = []
        classes_analyzed: list[str] = []
        snapshots: list[str] = []

        for file_path in interesting_files[:12]:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
            class_name = self._extract_class_name(text) or file_path.stem
            classes_analyzed.append(class_name)
            file_rules = self._extract_rules_from_text(class_name, text)
            rules.extend(file_rules)
            snapshots.append(f"FILE: {file_path.relative_to(source_root)}\n{text[:2500]}")

        deduped_rules = self._dedupe_preserve_order(rules)
        llm_result = self.enricher.enrich(
            file_snapshot="\n\n".join(snapshots[:6]),
            extracted_rules=deduped_rules[:20],
        )
        for rule in llm_result["additional_rules"]:
            if rule not in deduped_rules:
                deduped_rules.append(rule)

        artifact_path = artifact_dir / "05-business-rules.md"
        artifact_path.write_text(
            self._render_markdown(
                classes_analyzed=classes_analyzed,
                rules=deduped_rules,
                llm_summary=llm_result["summary"],
                llm_enabled=self.enricher.enabled,
            ),
            encoding="utf-8",
        )

        return BusinessLogicResult(
            rules=deduped_rules,
            classes_analyzed=classes_analyzed,
            artifact_path=artifact_path,
            llm_summary=llm_result["summary"],
        )

    def _is_business_logic_file(self, file_path: Path) -> bool:
        lowered = str(file_path).lower()
        return any(token in lowered for token in ("service", "controller", "manager", "handler"))

    def _extract_class_name(self, text: str) -> str | None:
        match = self.CLASS_PATTERN.search(text)
        return match.group(1) if match else None

    def _extract_rules_from_text(self, class_name: str, text: str) -> list[str]:
        rules: list[str] = []
        current_method = "class"

        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("//"):
                continue

            method_match = self.METHOD_PATTERN.search(line)
            if method_match:
                current_method = method_match.group(2)

            condition_match = self.CONDITION_PATTERN.search(line)
            if condition_match:
                rules.append(f"{class_name}.{current_method}: condition `{condition_match.group(1).strip()}`")

            throw_match = self.THROW_PATTERN.search(line)
            if throw_match:
                rules.append(
                    f"{class_name}.{current_method}: throws {throw_match.group(1)}"
                )

            if ".save(" in line or " save(" in line:
                rules.append(f"{class_name}.{current_method}: persists data")
            if ".delete(" in line or " delete(" in line:
                rules.append(f"{class_name}.{current_method}: deletes data")
            if ".find" in line or "findBy" in line:
                rules.append(f"{class_name}.{current_method}: queries existing data")
            if "send" in line.lower() and "(" in line:
                rules.append(f"{class_name}.{current_method}: triggers outbound communication")
            if "@Transactional" in line:
                rules.append(f"{class_name}: transactional workflow")

        return rules

    def _dedupe_preserve_order(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            if value not in seen:
                seen.add(value)
                result.append(value)
        return result

    def _render_markdown(
        self,
        *,
        classes_analyzed: list[str],
        rules: list[str],
        llm_summary: str | None,
        llm_enabled: bool,
    ) -> str:
        classes_text = "\n".join(f"- {name}" for name in classes_analyzed) or "- none"
        rules_text = "\n".join(f"- {rule}" for rule in rules) or "- none extracted"
        return (
            "# Business Rules\n\n"
            "## Classes Analyzed\n"
            f"{classes_text}\n\n"
            "## Extracted Rules\n"
            f"{rules_text}\n\n"
            "## LLM Enrichment\n"
            f"- Enabled: {'yes' if llm_enabled else 'no'}\n"
            f"- Summary: {llm_summary or 'none'}\n"
        )
