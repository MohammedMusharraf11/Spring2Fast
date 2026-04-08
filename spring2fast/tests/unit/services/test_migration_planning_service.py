"""Tests for migration plan generation."""

import asyncio
from pathlib import Path

from app.services.migration_planning_service import MigrationPlanningService


class _StubPlanningEnricher:
    async def enrich(self, **_kwargs):
        return {
            "implementation_steps": ["Generate dedicated user and product routers."],
            "risk_items": ["Admin login flow needs explicit regression coverage."],
            "target_files": ["app/api/v1/endpoints/users.py"],
        }


def test_migration_planning_service_creates_blueprint_and_artifact(tmp_path: Path) -> None:
    result = asyncio.run(MigrationPlanningService(enricher=_StubPlanningEnricher()).create_plan(
        artifacts_dir=str(tmp_path),
        discovered_technologies=["spring-boot", "spring-data-jpa", "spring-security", "redis"],
        business_rules=[
            "StudentController.saveStudentInformation: throws InvalidFieldException",
            "StudentService.createStudent: persists data",
        ],
        docs_references=[
            {"java_technology": "spring-boot", "python_equivalent": "fastapi", "official_docs": "https://fastapi.tiangolo.com/", "notes": "Web framework"},
        ],
    ))

    assert "app/main.py" in result.target_files
    assert "app/core/security.py" in result.target_files
    assert "app/repositories/__init__.py" in result.target_files
    assert "Dockerfile" in result.target_files
    assert "alembic.ini" in result.target_files
    assert "app/api/v1/endpoints/users.py" in result.target_files
    assert any("official Python-equivalent docs" in step for step in result.implementation_steps)
    assert any("dedicated user and product routers" in step for step in result.implementation_steps)
    assert any("Admin login flow" in item for item in result.risk_items)
    assert result.artifact_path.exists()
    assert "Migration Plan" in result.artifact_path.read_text(encoding="utf-8")
