"""Tests for generic component discovery."""

from pathlib import Path

from app.services.component_discovery_service import ComponentDiscoveryService


def test_component_discovery_service_discovers_generic_spring_components(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    java_dir = project_dir / "src" / "main" / "java" / "com" / "example"
    java_dir.mkdir(parents=True)

    (java_dir / "StudentController.java").write_text(
        """
        @RestController
        @RequestMapping("/student")
        public class StudentController {
            @GetMapping("/{id}")
            public String getStudent(@PathVariable Long id, @RequestHeader("student-auth-key") String authKey) { return "ok"; }

            @PostMapping
            public String saveStudentInformation(@RequestBody StudentRequestDto request) { return "ok"; }
        }
        """,
        encoding="utf-8",
    )
    (java_dir / "StudentService.java").write_text(
        """
        @Service
        public class StudentService {
            public void saveStudent() {}
        }
        """,
        encoding="utf-8",
    )
    (java_dir / "StudentRepository.java").write_text(
        """
        @Repository
        public class StudentRepository {}
        """,
        encoding="utf-8",
    )
    (java_dir / "Student.java").write_text(
        """
        @Entity
        public class Student {
            private Long id;
            private String name;
        }
        """,
        encoding="utf-8",
    )
    (java_dir / "StudentRequestDto.java").write_text(
        """
        public class StudentRequestDto {
            @NotBlank
            private String name;
            private Integer age;
        }
        """,
        encoding="utf-8",
    )

    result = ComponentDiscoveryService().discover(
        input_dir=str(project_dir),
        artifacts_dir=str(tmp_path / "artifacts"),
    )

    assert result.components["controllers"]
    assert result.components["services"]
    assert result.components["repositories"]
    assert result.components["entities"]
    controller = result.components["controllers"][0]
    entity = result.components["entities"][0]
    dto = result.components["dtos"][0]
    assert controller["method_details"][0]["parameters"][0]["name"] == "id"
    assert controller["method_details"][1]["parameters"][0]["type"] == "StudentRequestDto"
    assert entity["fields"][0]["name"] == "id"
    assert dto["fields"][0]["annotations"] == ["@NotBlank"]
    assert result.artifact_path.exists()
    assert "Component Inventory" in result.artifact_path.read_text(encoding="utf-8")
