"""Tests for Phase 3 feature wiring."""

import asyncio
from pathlib import Path

from app.agents.converter_agents.event_consumer_converter import event_consumer_converter_agent
from app.agents.converter_agents.feign_converter import feign_converter_agent
from app.agents.converter_agents.scheduler_converter import scheduler_converter_agent
from app.agents.converter_agents.base import BaseConverterAgent
from app.agents.generators.alembic_generator import AlembicGenerator
from app.agents.generators.sandbox_tester import SandboxTester
from app.agents.tools.converter_tools import parse_bean_validation
from app.agents.nodes.plan_migration import plan_migration_node


def test_parse_bean_validation_normalizes_dict_annotations() -> None:
    parsed = parse_bean_validation(
        [
            {
                "name": "email",
                "annotations": [{"name": "@NotNull"}, {"name": "Email"}],
            }
        ]
    )

    assert parsed["email"]["required"] is True
    assert parsed["email"]["format"] == "email"


def test_alembic_generator_uses_database_url_env_fallback(tmp_path: Path) -> None:
    result = AlembicGenerator().generate(
        output_dir=str(tmp_path),
        component_inventory={"entities": [{"class_name": "User"}]},
        discovered_technologies=["postgresql"],
    )

    env_text = (tmp_path / "alembic" / "env.py").read_text(encoding="utf-8")
    ini_text = (tmp_path / "alembic.ini").read_text(encoding="utf-8")

    assert "DATABASE_URL" in env_text
    assert "postgresql+asyncpg" in env_text
    assert "sqlalchemy.url = %(DATABASE_URL)s" in ini_text
    assert result.generated_files


def test_plan_migration_node_queues_phase3_components(tmp_path: Path) -> None:
    state = {
        "job_id": "job-phase3-plan",
        "source_type": "folder",
        "source_url": str(tmp_path),
        "workspace_dir": str(tmp_path),
        "input_dir": str(tmp_path / "input"),
        "artifacts_dir": str(tmp_path / "artifacts"),
        "output_dir": str(tmp_path / "output"),
        "status": "planning",
        "current_step": "Planning",
        "progress_pct": 50,
        "logs": [],
        "analysis_artifacts": {},
        "discovered_technologies": ["spring-boot", "kafka"],
        "business_rules": [],
        "generated_files": [],
        "validation_errors": [],
        "retry_count": 0,
        "metadata": {
            "docs_research": {"references": []},
            "component_inventory": {
                "feign_clients": [{"class_name": "UserServiceClient"}],
                "event_handlers": [{"class_name": "OrderListener"}],
                "scheduled_tasks": [{"class_name": "CleanupScheduler", "method_details": []}],
            },
        },
    }

    result = asyncio.run(plan_migration_node(state))
    queue_types = [item["type"] for item in result["conversion_queue"]]

    assert "feign_client" in queue_types
    assert "event_consumer" in queue_types
    assert "scheduled_task" in queue_types


def test_feign_converter_generates_httpx_client() -> None:
    code = feign_converter_agent._deterministic_convert(
        component={
            "class_name": "UserServiceClient",
            "method_details": [
                {
                    "name": "getUser",
                    "parameters": [{"name": "id", "annotations": ["@PathVariable"]}],
                    "raw_annotations": ['@GetMapping("/users/{id}")'],
                }
            ],
        },
        java_ir={},
        java_source='@FeignClient(name = "user-service", url = "${services.user.url}")',
    )

    assert "httpx.AsyncClient" in code
    assert "settings.services_user_url" in code
    assert "async def get_user" in code


def test_event_and_scheduler_converters_generate_runtime_modules() -> None:
    event_code = event_consumer_converter_agent._deterministic_convert(
        component={
            "class_name": "OrderListener",
            "method_details": [{"name": "consumeOrder", "raw_annotations": ['@KafkaListener(topics = "orders", groupId = "order-group")']}],
        },
        java_ir={},
        java_source='@KafkaListener(topics = "orders", groupId = "order-group")',
    )
    scheduler_code = scheduler_converter_agent._deterministic_convert(
        component={
            "class_name": "ApplicationScheduler",
            "tasks": [
                {
                    "class_name": "CleanupScheduler",
                    "method_details": [{"name": "cleanExpiredSessions", "raw_annotations": ['@Scheduled(fixedRate = 60000)']}],
                }
            ],
        },
        java_ir={},
        java_source="",
    )

    assert "AIOKafkaConsumer" in event_code
    assert "AsyncIOScheduler" in scheduler_code
    assert 'seconds=60' in scheduler_code


def test_sandbox_tester_builds_request_payloads_from_openapi() -> None:
    tester = SandboxTester()
    request = tester._build_request_kwargs(
        path="/api/v1/users/{id}",
        method="post",
        operation={
            "parameters": [{"name": "id", "in": "path", "schema": {"type": "integer"}}],
            "requestBody": {
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/UserCreate"}
                    }
                }
            },
        },
        schemas={
            "UserCreate": {
                "type": "object",
                "required": ["email"],
                "properties": {"email": {"type": "string", "format": "email"}, "name": {"type": "string"}},
            }
        },
    )

    assert request["path"] == "/api/v1/users/1"
    assert request["kwargs"]["json"]["email"] == "sandbox@example.com"


def test_stub_method_detection_flags_private_and_public_stub_bodies() -> None:
    code = """
class ExampleService:
    async def public_method(self):
        pass

    async def _private_helper(self):
        raise NotImplementedError()

    async def implemented(self):
        return {"ok": True}
"""

    stubs = BaseConverterAgent._has_stub_methods(code)

    assert "public_method" in stubs
    assert "_private_helper" in stubs
    assert "implemented" not in stubs


def test_phase3_prompt_builders_include_context() -> None:
    feign_prompt = feign_converter_agent._build_llm_prompt(
        java_source="interface UserClient {}",
        contract="client contract",
        existing_code={"clients": "class ExistingClient: pass"},
        discovered_technologies=["spring-cloud-openfeign"],
        docs_context="httpx docs",
        component={"class_name": "UserClient"},
    )
    event_prompt = event_consumer_converter_agent._build_llm_prompt(
        java_source="class OrderListener {}",
        contract="event contract",
        existing_code={"services": "class OrderService: pass"},
        discovered_technologies=["kafka"],
        docs_context="consumer docs",
        component={"class_name": "OrderListener"},
    )
    scheduler_prompt = scheduler_converter_agent._build_llm_prompt(
        java_source="class CleanupScheduler {}",
        contract="scheduler contract",
        existing_code={"services": "class CleanupService: pass"},
        discovered_technologies=["apscheduler"],
        docs_context="scheduler docs",
        component={"class_name": "CleanupScheduler"},
    )

    assert "interface UserClient" in feign_prompt
    assert "httpx docs" in feign_prompt
    assert "class ExistingClient: pass" in feign_prompt
    assert "class OrderService: pass" in event_prompt
    assert "consumer docs" in event_prompt
    assert "class CleanupService: pass" in scheduler_prompt
    assert "scheduler docs" in scheduler_prompt
