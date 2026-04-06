"""Planning utilities for building a target FastAPI migration blueprint."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.services.planning_llm_enricher import PlanningLLMEnricher


@dataclass(slots=True)
class MigrationPlanningResult:
    """Structured output for migration planning."""

    target_files: list[str]
    implementation_steps: list[str]
    risk_items: list[str]
    artifact_path: Path


class MigrationPlanningService:
    """Builds a FastAPI migration plan from discovered artifacts."""

    def __init__(self, enricher: PlanningLLMEnricher | None = None) -> None:
        self.enricher = enricher or PlanningLLMEnricher()

    def create_plan(
        self,
        *,
        artifacts_dir: str,
        discovered_technologies: list[str],
        business_rules: list[str],
        docs_references: list[dict[str, str]],
    ) -> MigrationPlanningResult:
        """Generate a target-file blueprint and execution plan."""
        artifact_dir = Path(artifacts_dir)
        artifact_dir.mkdir(parents=True, exist_ok=True)

        target_files = self._build_target_files(discovered_technologies)
        implementation_steps = self._build_implementation_steps(
            discovered_technologies=discovered_technologies,
            business_rules=business_rules,
            docs_references=docs_references,
        )
        risk_items = self._build_risk_items(
            discovered_technologies=discovered_technologies,
            business_rules=business_rules,
        )
        llm_result = self.enricher.enrich(
            discovered_technologies=discovered_technologies,
            business_rules=business_rules,
            docs_references=docs_references,
            target_files=target_files,
        )
        target_files = self._merge_unique(target_files, llm_result["target_files"])
        implementation_steps = self._merge_unique(implementation_steps, llm_result["implementation_steps"])
        risk_items = self._merge_unique(risk_items, llm_result["risk_items"])

        artifact_path = artifact_dir / "07-migration-plan.md"
        artifact_path.write_text(
            self._render_markdown(
                target_files=target_files,
                implementation_steps=implementation_steps,
                risk_items=risk_items,
            ),
            encoding="utf-8",
        )

        return MigrationPlanningResult(
            target_files=target_files,
            implementation_steps=implementation_steps,
            risk_items=risk_items,
            artifact_path=artifact_path,
        )

    def _merge_unique(self, base: list[str], extra: list[str]) -> list[str]:
        seen = set(base)
        merged = list(base)
        for item in extra:
            if item not in seen:
                seen.add(item)
                merged.append(item)
        return merged

    def _build_target_files(self, discovered_technologies: list[str]) -> list[str]:
        files = [
            "app/main.py",
            "app/api/v1/router.py",
            "app/api/v1/endpoints/health.py",
            "app/api/v1/endpoints/migration.py",
            "app/core/config.py",
            "app/db/session.py",
            "app/schemas/__init__.py",
            "app/services/__init__.py",
        ]
        if "spring-data-jpa" in discovered_technologies or "hibernate" in discovered_technologies:
            files.extend(
                [
                    "app/db/base.py",
                    "app/models/__init__.py",
                    "app/repositories/__init__.py",
                ]
            )
        if "spring-security" in discovered_technologies or "jwt" in discovered_technologies:
            files.extend(
                [
                    "app/core/security.py",
                    "app/api/deps.py",
                ]
            )
        if any(tech in discovered_technologies for tech in ("feign", "webclient", "resttemplate", "supabase", "redis", "kafka", "rabbitmq")):
            files.append("app/integrations/__init__.py")
        return files

    def _build_implementation_steps(
        self,
        *,
        discovered_technologies: list[str],
        business_rules: list[str],
        docs_references: list[dict[str, str]],
    ) -> list[str]:
        steps = [
            "Create the FastAPI project skeleton and base configuration files.",
            "Translate controllers into FastAPI routers while preserving endpoint behavior.",
            "Translate service-layer workflows into Python services with preserved validations and branching.",
        ]
        if "spring-data-jpa" in discovered_technologies or "hibernate" in discovered_technologies:
            steps.append("Model JPA entities and repositories using SQLAlchemy ORM and repository helpers.")
        if "spring-security" in discovered_technologies:
            steps.append("Recreate authentication and authorization flows with FastAPI security dependencies.")
        if docs_references:
            steps.append("Use official Python-equivalent docs references to guide library-specific implementations.")
        if business_rules:
            steps.append("Validate generated code against extracted business rules before final packaging.")
        return steps

    def _build_risk_items(
        self,
        *,
        discovered_technologies: list[str],
        business_rules: list[str],
    ) -> list[str]:
        risks: list[str] = []
        if "spring-security" in discovered_technologies:
            risks.append("Security behavior may require manual verification for auth filters, header rules, and role checks.")
        if any(tech in discovered_technologies for tech in ("kafka", "rabbitmq", "redis", "supabase")):
            risks.append("External integration behavior should be validated against live service contracts after migration.")
        if len(business_rules) > 10:
            risks.append("High business-rule count indicates service workflows should be reviewed with targeted regression tests.")
        if not risks:
            risks.append("Primary migration risk is preserving behavioral parity across controllers and services.")
        return risks

    def _render_markdown(
        self,
        *,
        target_files: list[str],
        implementation_steps: list[str],
        risk_items: list[str],
    ) -> str:
        target_text = "\n".join(f"- {path}" for path in target_files) or "- none"
        step_text = "\n".join(f"- {step}" for step in implementation_steps) or "- none"
        risk_text = "\n".join(f"- {item}" for item in risk_items) or "- none"
        return (
            "# Migration Plan\n\n"
            "## Target FastAPI Files\n"
            f"{target_text}\n\n"
            "## Implementation Steps\n"
            f"{step_text}\n\n"
            "## Risks\n"
            f"{risk_text}\n"
        )
