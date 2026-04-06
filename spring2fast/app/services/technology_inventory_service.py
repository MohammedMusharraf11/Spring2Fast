"""Source scanning utilities for Java technology discovery."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from app.services.technology_llm_enricher import TechnologyLLMEnricher


@dataclass(slots=True)
class TechnologyInventoryResult:
    """Structured output from a source tree technology scan."""

    technologies: list[str]
    build_systems: list[str]
    java_file_count: int
    build_files: list[str]
    notes: list[str]
    artifact_path: Path
    llm_summary: str | None


class TechnologyInventoryService:
    """Scans an ingested source tree for Java ecosystem technologies."""

    _PATTERNS = {
        "spring-boot": [r"spring-boot", r"@SpringBootApplication"],
        "spring-web": [r"spring-web", r"spring-boot-starter-web", r"@RestController"],
        "spring-data-jpa": [r"spring-boot-starter-data-jpa", r"javax\.persistence", r"jakarta\.persistence"],
        "hibernate": [r"hibernate"],
        "spring-security": [r"spring-boot-starter-security", r"@EnableWebSecurity", r"SecurityFilterChain"],
        "postgresql": [r"org\.postgresql", r"postgresql", r"jdbc:postgresql"],
        "mysql": [r"mysql", r"jdbc:mysql"],
        "mongodb": [r"mongodb", r"spring-boot-starter-data-mongodb"],
        "redis": [r"redis", r"spring-boot-starter-data-redis"],
        "kafka": [r"kafka", r"spring-kafka"],
        "rabbitmq": [r"rabbitmq", r"spring-boot-starter-amqp"],
        "supabase": [r"supabase"],
        "aws": [r"aws", r"software\.amazon\.awssdk", r"spring-cloud-aws"],
        "gcp": [r"google-cloud", r"gcp", r"com\.google\.cloud"],
        "azure": [r"azure"],
        "openapi-swagger": [r"springdoc-openapi", r"swagger", r"openapi"],
        "lombok": [r"lombok"],
        "mapstruct": [r"mapstruct"],
        "feign": [r"openfeign", r"feign"],
        "webclient": [r"WebClient"],
        "resttemplate": [r"RestTemplate"],
        "docker": [r"docker", r"FROM ", r"docker-compose"],
    }

    def __init__(self, enricher: TechnologyLLMEnricher | None = None) -> None:
        self.enricher = enricher or TechnologyLLMEnricher()

    def scan_project(self, *, input_dir: str, artifacts_dir: str) -> TechnologyInventoryResult:
        """Scan a project tree and write a markdown inventory artifact."""
        source_root = Path(input_dir)
        artifact_dir = Path(artifacts_dir)
        artifact_dir.mkdir(parents=True, exist_ok=True)

        all_text = self._collect_search_text(source_root)
        technologies = self._detect_technologies(all_text)
        build_files = self._find_build_files(source_root)
        build_systems = self._detect_build_systems(build_files)
        java_file_count = len(list(source_root.rglob("*.java")))
        notes = self._build_notes(source_root, build_files, java_file_count)
        file_snapshot = self._build_file_snapshot(source_root)
        llm_result = self.enricher.enrich(
            file_snapshot=file_snapshot,
            detected_technologies=technologies,
            build_files=build_files,
            java_file_count=java_file_count,
        )

        for technology in llm_result["additional_technologies"]:
            if technology not in technologies:
                technologies.append(technology)
        technologies = sorted(technologies)
        notes = [*notes, *llm_result["notes"]]

        artifact_path = artifact_dir / "02-technology-inventory.md"
        artifact_path.write_text(
            self._render_markdown(
                source_root=source_root,
                technologies=technologies,
                build_systems=build_systems,
                java_file_count=java_file_count,
                build_files=build_files,
                notes=notes,
                llm_summary=llm_result["summary"],
                llm_enabled=self.enricher.enabled,
            ),
            encoding="utf-8",
        )

        return TechnologyInventoryResult(
            technologies=technologies,
            build_systems=build_systems,
            java_file_count=java_file_count,
            build_files=build_files,
            notes=notes,
            artifact_path=artifact_path,
            llm_summary=llm_result["summary"],
        )

    def _collect_search_text(self, source_root: Path) -> str:
        parts: list[str] = []
        candidate_files = [
            *source_root.rglob("pom.xml"),
            *source_root.rglob("build.gradle"),
            *source_root.rglob("build.gradle.kts"),
            *source_root.rglob("application.properties"),
            *source_root.rglob("application.yml"),
            *source_root.rglob("application.yaml"),
            *source_root.rglob("*.java"),
            *source_root.rglob("Dockerfile"),
            *source_root.rglob("docker-compose*.yml"),
        ]

        for file_path in candidate_files:
            if ".git" in file_path.parts:
                continue
            try:
                parts.append(file_path.read_text(encoding="utf-8", errors="ignore"))
            except OSError:
                continue

        return "\n".join(parts)

    def _detect_technologies(self, all_text: str) -> list[str]:
        detected: list[str] = []
        for technology, patterns in self._PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, all_text, re.IGNORECASE):
                    detected.append(technology)
                    break
        return sorted(detected)

    def _find_build_files(self, source_root: Path) -> list[str]:
        build_files: list[str] = []
        for pattern in ("pom.xml", "build.gradle", "build.gradle.kts"):
            for file_path in source_root.rglob(pattern):
                if ".git" not in file_path.parts:
                    build_files.append(str(file_path.relative_to(source_root)))
        return sorted(build_files)

    def _detect_build_systems(self, build_files: list[str]) -> list[str]:
        systems: list[str] = []
        if any(path.endswith("pom.xml") for path in build_files):
            systems.append("maven")
        if any(path.endswith("build.gradle") or path.endswith("build.gradle.kts") for path in build_files):
            systems.append("gradle")
        return systems

    def _build_notes(self, source_root: Path, build_files: list[str], java_file_count: int) -> list[str]:
        notes = [
            f"Java source files detected: {java_file_count}",
            f"Build files detected: {len(build_files)}",
        ]
        if (source_root / "src" / "main" / "resources").exists():
            notes.append("Spring resource directory detected under src/main/resources")
        if any((source_root / name).exists() for name in ("Dockerfile", "docker-compose.yml", "docker-compose.yaml")):
            notes.append("Container configuration files detected at project root")
        return notes

    def _build_file_snapshot(self, source_root: Path) -> str:
        snapshots: list[str] = []
        for file_path in [
            *source_root.rglob("pom.xml"),
            *source_root.rglob("build.gradle"),
            *source_root.rglob("build.gradle.kts"),
            *source_root.rglob("application.properties"),
            *source_root.rglob("application.yml"),
            *source_root.rglob("application.yaml"),
            *source_root.rglob("*.java"),
        ][:8]:
            if ".git" in file_path.parts:
                continue
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            snapshots.append(
                f"FILE: {file_path.relative_to(source_root)}\n{content[:2000]}"
            )
        return "\n\n".join(snapshots)

    def _render_markdown(
        self,
        *,
        source_root: Path,
        technologies: list[str],
        build_systems: list[str],
        java_file_count: int,
        build_files: list[str],
        notes: list[str],
        llm_summary: str | None,
        llm_enabled: bool,
    ) -> str:
        technology_lines = "\n".join(f"- {item}" for item in technologies) or "- none detected"
        build_lines = "\n".join(f"- {item}" for item in build_systems) or "- none detected"
        build_file_lines = "\n".join(f"- {item}" for item in build_files) or "- none detected"
        note_lines = "\n".join(f"- {item}" for item in notes) or "- none"
        llm_section = (
            "## LLM Enrichment\n"
            f"- Enabled: {'yes' if llm_enabled else 'no'}\n"
            f"- Summary: {llm_summary or 'none'}\n\n"
        )
        return (
            "# Technology Inventory\n\n"
            f"- Source root: `{source_root}`\n"
            f"- Java file count: {java_file_count}\n\n"
            "## Build Systems\n"
            f"{build_lines}\n\n"
            "## Build Files\n"
            f"{build_file_lines}\n\n"
            "## Detected Technologies\n"
            f"{technology_lines}\n\n"
            f"{llm_section}"
            "## Notes\n"
            f"{note_lines}\n"
        )
