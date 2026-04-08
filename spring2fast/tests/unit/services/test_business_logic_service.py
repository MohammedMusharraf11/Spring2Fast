"""Tests for business logic extraction."""

import asyncio
from pathlib import Path

from app.services.business_logic_service import BusinessLogicService


class _StubEnricher:
    enabled = True

    async def enrich(self, **_kwargs):
        return {
            "summary": "The service validates user uniqueness, persists records, and sends notifications.",
            "additional_rules": ["UserService.createUser: sends welcome notification after persistence"],
        }


def test_business_logic_service_extracts_rules_and_writes_artifact(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    artifacts_dir = tmp_path / "artifacts"
    service_dir = project_dir / "src" / "main" / "java" / "com" / "example" / "service"
    service_dir.mkdir(parents=True)
    (service_dir / "UserService.java").write_text(
        """
        @Transactional
        public class UserService {
            public User createUser(UserRequest request) {
                if (userRepository.findByEmail(request.getEmail()).isPresent()) {
                    throw new IllegalArgumentException("Email already exists");
                }
                User user = userRepository.save(new User());
                emailService.sendWelcomeEmail(user);
                return user;
            }
        }
        """,
        encoding="utf-8",
    )

    result = asyncio.run(BusinessLogicService(enricher=_StubEnricher()).extract(
        input_dir=str(project_dir),
        artifacts_dir=str(artifacts_dir),
    ))

    assert "UserService: transactional workflow" in result.rules
    assert any("condition" in rule for rule in result.rules)
    assert any("throws IllegalArgumentException" in rule for rule in result.rules)
    assert any("persists data" in rule for rule in result.rules)
    assert any("welcome notification" in rule for rule in result.rules)
    assert result.artifact_path.exists()
    assert "LLM Enrichment" in result.artifact_path.read_text(encoding="utf-8")
