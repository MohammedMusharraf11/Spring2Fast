"""Tests for official-docs research mapping."""

import asyncio
from pathlib import Path

from app.services.docs_research_service import DocsResearchService


class _StubGoogleSearchService:
    def __init__(self) -> None:
        self.calls = 0

    def search(self, *, query: str, num_results: int = 5):
        self.calls += 1
        return [
            {
                "title": "FastAPI Docs",
                "url": "https://fastapi.tiangolo.com/",
                "snippet": query,
                "source": "serper_search",
            }
        ]


class _StubMCPResearchService:
    def __init__(self) -> None:
        self.calls = 0

    def search(self, *, query: str):
        self.calls += 1
        return [
            {
                "title": "SQLAlchemy ORM",
                "url": "https://docs.sqlalchemy.org/en/20/orm/",
                "snippet": query,
                "source": "mcp",
            }
        ]


class _StubDocsEnricher:
    async def enrich_batch(self, *, candidates):
        results = []
        for candidate in candidates:
            static_reference = candidate.get("static_reference") or {}
            google_results = candidate.get("google_results", [])
            mcp_results = candidate.get("mcp_results", [])
            results.append(
                {
                    "java_technology": candidate["java_technology"],
                    "python_equivalent": static_reference.get("python_equivalent") or candidate["java_technology"],
                    "official_docs": static_reference.get("official_docs") or (google_results[0]["url"] if google_results else ""),
                    "notes": f"Google:{len(google_results)} MCP:{len(mcp_results)}",
                }
            )
        return results


def test_docs_research_service_builds_official_reference_artifact(tmp_path: Path) -> None:
    search_service = _StubGoogleSearchService()
    mcp_service = _StubMCPResearchService()
    result = asyncio.run(DocsResearchService(
        search_service=search_service,
        mcp_research_service=mcp_service,
        enricher=_StubDocsEnricher(),
    ).build_references(
        technologies=["spring-boot", "spring-data-jpa", "redis", "supabase"],
        artifacts_dir=str(tmp_path),
    ))

    assert len(result.references) == 4
    assert result.artifact_path.exists()
    text = result.artifact_path.read_text(encoding="utf-8")
    assert "https://fastapi.tiangolo.com/" in text
    assert "https://docs.sqlalchemy.org/en/20/" in text
    assert "https://redis.readthedocs.io/en/stable/" in text
    assert "https://supabase.com/docs/reference/python/introduction" in text
    assert "Google results used: 0" in text
    assert "MCP results used: 0" in text
    assert search_service.calls == 1
    assert mcp_service.calls == 1
