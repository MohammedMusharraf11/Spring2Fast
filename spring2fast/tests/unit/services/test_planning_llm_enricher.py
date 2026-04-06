"""Tests for optional planning LLM enrichment."""

from app.services.planning_llm_enricher import PlanningLLMEnricher


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeModel:
    def invoke(self, _messages):
        return _FakeResponse(
            '{"implementation_steps":["Generate repository-specific routers."],"risk_items":["Custom auth flow needs regression tests."],"target_files":["app/api/v1/endpoints/users.py"]}'
        )


def test_planning_llm_enricher_parses_json_response() -> None:
    enricher = PlanningLLMEnricher(model=_FakeModel())

    result = enricher.enrich(
        discovered_technologies=["spring-security"],
        business_rules=["UserServices.validateLoginCredentials: condition `u!=null`"],
        docs_references=[],
        target_files=["app/main.py"],
    )

    assert "Generate repository-specific routers." in result["implementation_steps"]
    assert "Custom auth flow needs regression tests." in result["risk_items"]
    assert "app/api/v1/endpoints/users.py" in result["target_files"]
