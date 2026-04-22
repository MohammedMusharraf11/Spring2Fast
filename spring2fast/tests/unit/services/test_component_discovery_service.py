"""Tests for generic component discovery."""

from pathlib import Path
from unittest.mock import Mock

from app.services.component_discovery_service import ComponentDiscoveryService, LLMComponentEnricher


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


def test_component_discovery_service_resolves_mapped_superclass_fields(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    java_dir = project_dir / "src" / "main" / "java" / "com" / "example"
    java_dir.mkdir(parents=True)

    (java_dir / "Person.java").write_text(
        """
        @MappedSuperclass
        public class Person {
            @Id
            private Long id;

            @NotBlank
            private String firstName;
        }
        """,
        encoding="utf-8",
    )
    (java_dir / "Owner.java").write_text(
        """
        @Entity
        public class Owner extends Person {
            private String lastName;
        }
        """,
        encoding="utf-8",
    )

    result = ComponentDiscoveryService().discover(
        input_dir=str(project_dir),
        artifacts_dir=str(tmp_path / "artifacts"),
    )

    owner = result.components["entities"][0]
    inherited_names = [field["name"] for field in owner["inherited_fields"]]
    all_names = [field["name"] for field in owner["all_fields"]]

    assert owner["superclass_chain"] == ["Person"]
    assert inherited_names == ["id", "firstName"]
    assert all_names == ["id", "firstName", "lastName"]
    assert owner["bean_validation_summary"]


def test_component_discovery_service_writes_ground_truth_json(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    java_dir = project_dir / "src" / "main" / "java" / "com" / "example"
    java_dir.mkdir(parents=True)

    (java_dir / "UserController.java").write_text(
        """
        @RestController
        public class UserController {
            @GetMapping("/{id}")
            public String getUser(@PathVariable Long id) { return "ok"; }
        }
        """,
        encoding="utf-8",
    )
    (java_dir / "UserService.java").write_text(
        """
        @Service
        public class UserService {
            public void syncUser() {}
        }
        """,
        encoding="utf-8",
    )

    ComponentDiscoveryService().discover(
        input_dir=str(project_dir),
        artifacts_dir=str(tmp_path / "artifacts"),
    )

    ground_truth_path = tmp_path / "artifacts" / "ground_truth.json"
    ground_truth = ground_truth_path.read_text(encoding="utf-8")

    assert ground_truth_path.exists()
    assert '"controllers": [' in ground_truth
    assert '"UserController"' in ground_truth
    assert '"services": [' in ground_truth
    assert '"UserService"' in ground_truth


def test_component_discovery_service_classifies_controller_advice_correctly() -> None:
    service = ComponentDiscoveryService()

    category = service._classify_component(
        Path("GlobalExceptionHandler.java"),
        """
        @ControllerAdvice
        public class GlobalExceptionHandler {}
        """,
    )

    assert category == "exception_handlers"


def test_component_discovery_service_extracts_real_class_not_loop_keyword(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    java_dir = project_dir / "src" / "main" / "java" / "com" / "example"
    java_dir.mkdir(parents=True)

    (java_dir / "VetRepository.java").write_text(
        """
        package com.example;

        public class VetRepository {
            public void iterate() {
                for (int i = 0; i < 1; i++) {
                }
            }
        }
        """,
        encoding="utf-8",
    )

    result = ComponentDiscoveryService().discover(
        input_dir=str(project_dir),
        artifacts_dir=str(tmp_path / "artifacts"),
    )

    ground_truth = (tmp_path / "artifacts" / "ground_truth.json").read_text(encoding="utf-8")
    assert "VetRepository" in ground_truth
    assert "for" not in ground_truth


def test_llm_component_enricher_maps_unknown_files_into_inventory() -> None:
    service = ComponentDiscoveryService()
    mock_model = Mock()
    mock_model.invoke.return_value = Mock(content='{"src/main/java/com/example/CustomerRecord.java": "entity"}')
    enricher = LLMComponentEnricher(service, model=mock_model)

    result = enricher.enrich_unclassified(
        unclassified=[
            {
                "class_name": "CustomerRecord",
                "file_path": "src/main/java/com/example/CustomerRecord.java",
                "source": "public class CustomerRecord { private Long id; private String email; }",
            }
        ],
        inventory={"entities": [], "services": []},
    )

    assert "entities" in result
    assert result["entities"][0]["class_name"] == "CustomerRecord"
