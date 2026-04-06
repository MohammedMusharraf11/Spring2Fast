"""Tests for the output generation node."""

from pathlib import Path

from app.agents.nodes.generate_output import generate_output_node


def test_generate_output_node_updates_state_and_writes_output(tmp_path: Path) -> None:
    output_dir = tmp_path / "output"
    artifacts_dir = tmp_path / "artifacts"
    input_dir = tmp_path / "input"
    output_dir.mkdir()
    artifacts_dir.mkdir()
    input_dir.mkdir()

    state = {
        "job_id": "job-output",
        "source_type": "folder",
        "source_url": "https://github.com/example/repo",
        "workspace_dir": str(tmp_path),
        "input_dir": str(input_dir),
        "artifacts_dir": str(artifacts_dir),
        "output_dir": str(output_dir),
        "status": "planning",
        "current_step": "Created FastAPI migration blueprint",
        "progress_pct": 60,
        "logs": [],
        "analysis_artifacts": {},
        "discovered_technologies": ["spring-boot", "spring-security", "mysql"],
        "business_rules": ["OrderService.submitOrder: persists data"],
        "generated_files": [],
        "validation_errors": [],
        "retry_count": 0,
        "metadata": {
            "component_inventory": {
                "controllers": [
                    {
                        "class_name": "StudentController",
                        "methods": ["getStudent"],
                        "request_mappings": ['@GetMapping("/students")'],
                    }
                ],
                "services": [{"class_name": "StudentService", "methods": ["saveStudent"]}],
                "repositories": [{"class_name": "StudentRepository", "methods": ["findById"]}],
                "entities": [{"class_name": "Student", "methods": []}],
                "dtos": [{"class_name": "StudentRequestDto", "methods": []}],
                "exception_handlers": [{"class_name": "GlobalExceptionHandler", "methods": []}],
            },
            "migration_plan": {
                "target_files": [
                    "app/main.py",
                    "app/core/config.py",
                    "app/db/session.py",
                    "app/core/security.py",
                ],
                "implementation_steps": ["Create the FastAPI project skeleton."],
                "risk_items": ["Security behavior may require manual verification."],
            }
        },
    }

    result = generate_output_node(state)

    assert result["status"] == "migrating"
    assert result["progress_pct"] == 80
    assert result["generated_files"]
    assert (output_dir / "app" / "main.py").exists()
    assert (output_dir / "app" / "api" / "v1" / "endpoints" / "student.py").exists()
    assert (output_dir / "app" / "services" / "student_service.py").exists()
    assert (output_dir / "app" / "repositories" / "student_repository.py").exists()
    assert (output_dir / "app" / "models" / "student.py").exists()
    assert (output_dir / "app" / "schemas" / "student_request_dto.py").exists()
    assert "output_root" in result["metadata"]["output_generation"]
