"""Tests for output scaffold generation."""

import asyncio
from pathlib import Path

from app.services.output_generation_service import OutputGenerationService


def test_output_generation_service_creates_fastapi_scaffold(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    result = asyncio.run(OutputGenerationService().generate_scaffold(
        output_dir=str(tmp_path / "output"),
        input_dir=str(input_dir),
        target_files=[
            "app/main.py",
            "app/core/config.py",
            "app/db/session.py",
            "app/core/security.py",
        ],
        implementation_steps=["Create the FastAPI project skeleton."],
        discovered_technologies=["spring-security", "mysql", "bcrypt"],
        business_rules=["UserServices.validateLoginCredentials: condition `u!=null`"],
        source_url="https://github.com/example/repo",
        component_inventory={
            "controllers": [
                {
                    "class_name": "StudentController",
                    "methods": ["getStudent", "createStudent"],
                    "request_mappings": ['@RequestMapping("/students")'],
                    "method_details": [
                        {
                            "name": "getStudent",
                            "return_type": "StudentResponseDto",
                            "parameters": [
                                {"name": "id", "type": "Long", "annotations": ["@PathVariable"]},
                                {"name": "authKey", "type": "String", "annotations": ['@RequestHeader("student-auth-key")']},
                            ],
                            "mapping_annotations": ['@GetMapping("/{id}")'],
                        },
                        {
                            "name": "createStudent",
                            "return_type": "StudentResponseDto",
                            "parameters": [
                                {"name": "request", "type": "StudentRequestDto", "annotations": ["@RequestBody"]},
                            ],
                            "mapping_annotations": ['@PostMapping'],
                        },
                    ],
                }
            ],
            "services": [{"class_name": "StudentService", "methods": ["getStudent", "saveStudent", "deleteStudent"]}],
            "repositories": [{"class_name": "StudentRepository", "methods": ["findById", "findAll", "save", "deleteById", "existsByName"]}],
            "entities": [{"class_name": "Student", "methods": [], "fields": [{"name": "id", "type": "Long"}, {"name": "name", "type": "String"}]}],
            "dtos": [
                {
                    "class_name": "StudentRequestDto",
                    "methods": [],
                    "fields": [
                        {"name": "name", "type": "String", "annotations": ["@NotBlank"]},
                        {"name": "age", "type": "Integer", "annotations": []},
                    ],
                }
            ],
            "exception_handlers": [{"class_name": "GlobalExceptionHandler", "methods": ["handleError"]}],
        },
    ))

    output_root = Path(result.output_root)
    assert (output_root / "app" / "main.py").exists()
    assert (output_root / "app" / "core" / "security.py").exists()
    assert (output_root / "app" / "api" / "v1" / "endpoints" / "student.py").exists()
    assert (output_root / "app" / "services" / "student_service.py").exists()
    assert (output_root / "app" / "repositories" / "student_repository.py").exists()
    assert (output_root / "app" / "models" / "student.py").exists()
    assert (output_root / "app" / "schemas" / "student_request_dto.py").exists()
    assert (output_root / "requirements.txt").exists()
    assert (output_root / "README.md").exists()
    assert "pymysql" in (output_root / "requirements.txt").read_text(encoding="utf-8")
    assert "passlib[bcrypt]" in (output_root / "requirements.txt").read_text(encoding="utf-8")
    router_text = (output_root / "app" / "api" / "v1" / "router.py").read_text(encoding="utf-8")
    controller_text = (output_root / "app" / "api" / "v1" / "endpoints" / "student.py").read_text(encoding="utf-8")
    schema_text = (output_root / "app" / "schemas" / "student_request_dto.py").read_text(encoding="utf-8")
    model_text = (output_root / "app" / "models" / "student.py").read_text(encoding="utf-8")
    service_text = (output_root / "app" / "services" / "student_service.py").read_text(encoding="utf-8")
    repository_text = (output_root / "app" / "repositories" / "student_repository.py").read_text(encoding="utf-8")
    assert "student_router" in router_text
    assert "APIRouter" in controller_text
    assert "BaseModel" in schema_text
    assert "mapped_column" in model_text
    assert "class StudentService" in service_text
    assert "class StudentRepository" in repository_text
