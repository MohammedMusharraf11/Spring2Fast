"""Tests for optional technology discovery LLM enrichment."""

from app.services.technology_llm_enricher import TechnologyLLMEnricher


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeModel:
    def invoke(self, _messages):
        return _FakeResponse(
            '{"summary":"Detected likely persistence and auth stack.","additional_technologies":["jwt","postgresql"],"notes":["LLM inferred JWT usage from security config."]}'
        )


def test_llm_enricher_parses_json_response() -> None:
    enricher = TechnologyLLMEnricher(model=_FakeModel())

    result = enricher.enrich(
        file_snapshot="SecurityConfig.java ... JwtDecoder ...",
        detected_technologies=["spring-security"],
        build_files=["pom.xml"],
        java_file_count=12,
    )

    assert result["summary"] == "Detected likely persistence and auth stack."
    assert "jwt" in result["additional_technologies"]
    assert "postgresql" in result["additional_technologies"]
