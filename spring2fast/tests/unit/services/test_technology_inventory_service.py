"""Tests for technology discovery scanning."""

from pathlib import Path

from app.services.technology_inventory_service import TechnologyInventoryService


class _StubEnricher:
    enabled = True

    def enrich(self, **_kwargs):
        return {
            "summary": "The project likely uses JWT-based authentication and PostgreSQL.",
            "additional_technologies": ["jwt"],
            "notes": ["LLM noticed auth-related configuration in source snippets."],
        }


def test_technology_inventory_service_detects_java_stack(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    artifacts_dir = tmp_path / "artifacts"
    (project_dir / "src" / "main" / "java" / "com" / "example").mkdir(parents=True)
    (project_dir / "src" / "main" / "resources").mkdir(parents=True)
    (project_dir / "pom.xml").write_text(
        """
        <project>
          <dependencies>
            <dependency><artifactId>spring-boot-starter-web</artifactId></dependency>
            <dependency><artifactId>spring-boot-starter-data-jpa</artifactId></dependency>
            <dependency><artifactId>spring-boot-starter-security</artifactId></dependency>
            <dependency><artifactId>supabase-java</artifactId></dependency>
            <dependency><artifactId>postgresql</artifactId></dependency>
          </dependencies>
        </project>
        """,
        encoding="utf-8",
    )
    (project_dir / "src" / "main" / "java" / "com" / "example" / "UserController.java").write_text(
        """
        import org.springframework.web.bind.annotation.RestController;
        @RestController
        public class UserController {}
        """,
        encoding="utf-8",
    )

    result = TechnologyInventoryService(enricher=_StubEnricher()).scan_project(
        input_dir=str(project_dir),
        artifacts_dir=str(artifacts_dir),
    )

    assert "maven" in result.build_systems
    assert "spring-web" in result.technologies
    assert "spring-data-jpa" in result.technologies
    assert "spring-security" in result.technologies
    assert "supabase" in result.technologies
    assert "postgresql" in result.technologies
    assert "jwt" in result.technologies
    assert result.java_file_count == 1
    assert result.artifact_path.exists()
    artifact_text = result.artifact_path.read_text(encoding="utf-8")
    assert "Technology Inventory" in artifact_text
    assert "LLM Enrichment" in artifact_text
    assert "Enabled: yes" in artifact_text
