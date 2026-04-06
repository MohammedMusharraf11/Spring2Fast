"""Official documentation mapping for Python migration targets."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.services.docs_research_llm_enricher import DocsResearchLLMEnricher
from app.services.mcp_research_service import MCPResearchService
from app.services.serper_search_service import SerperSearchService


@dataclass(slots=True)
class DocsResearchResult:
    """Structured output for official docs research."""

    references: list[dict[str, str]]
    artifact_path: Path


class DocsResearchService:
    """Maps discovered Java technologies to Python-equivalent docs, with dynamic enrichment."""

    _DYNAMIC_RESEARCH_TECHS = {
        "supabase",
        "feign",
        "webclient",
        "resttemplate",
        "kafka",
        "rabbitmq",
        "mongodb",
    }

    _REFERENCE_MAP = {
        "spring-boot": {
            "python_equivalent": "fastapi",
            "official_docs": "https://fastapi.tiangolo.com/",
            "notes": "Primary Python web framework target for backend migration.",
        },
        "spring-web": {
            "python_equivalent": "fastapi-routing",
            "official_docs": "https://fastapi.tiangolo.com/tutorial/path-operation-configuration/",
            "notes": "Maps REST controllers and route handling to FastAPI path operations.",
        },
        "spring-data-jpa": {
            "python_equivalent": "sqlalchemy",
            "official_docs": "https://docs.sqlalchemy.org/en/20/",
            "notes": "Primary ORM and persistence layer equivalent.",
        },
        "hibernate": {
            "python_equivalent": "sqlalchemy-orm",
            "official_docs": "https://docs.sqlalchemy.org/en/20/orm/",
            "notes": "Equivalent ORM concepts and entity relationships.",
        },
        "spring-security": {
            "python_equivalent": "fastapi-security",
            "official_docs": "https://fastapi.tiangolo.com/tutorial/security/",
            "notes": "Authentication and authorization patterns in FastAPI.",
        },
        "jakarta-validation": {
            "python_equivalent": "pydantic",
            "official_docs": "https://docs.pydantic.dev/latest/",
            "notes": "Pydantic models and validation rules map well from Jakarta Bean Validation.",
        },
        "jwt": {
            "python_equivalent": "pyjwt",
            "official_docs": "https://pyjwt.readthedocs.io/en/stable/",
            "notes": "JWT encode/decode support for token-based auth.",
        },
        "bcrypt": {
            "python_equivalent": "passlib-bcrypt",
            "official_docs": "https://passlib.readthedocs.io/en/stable/lib/passlib.hash.bcrypt.html",
            "notes": "Password hashing equivalent for authentication flows.",
        },
        "postgresql": {
            "python_equivalent": "sqlalchemy-postgresql",
            "official_docs": "https://docs.sqlalchemy.org/en/20/dialects/postgresql.html",
            "notes": "PostgreSQL dialect and database integration guidance.",
        },
        "mysql": {
            "python_equivalent": "sqlalchemy-mysql",
            "official_docs": "https://docs.sqlalchemy.org/en/20/dialects/mysql.html",
            "notes": "MySQL dialect support for SQLAlchemy.",
        },
        "mongodb": {
            "python_equivalent": "pymongo",
            "official_docs": "https://www.mongodb.com/docs/languages/python/pymongo-driver/current/",
            "notes": "Official MongoDB Python driver docs.",
        },
        "redis": {
            "python_equivalent": "redis-py",
            "official_docs": "https://redis.readthedocs.io/en/stable/",
            "notes": "Official Python Redis client documentation.",
        },
        "kafka": {
            "python_equivalent": "aiokafka",
            "official_docs": "https://aiokafka.readthedocs.io/en/stable/",
            "notes": "Async Kafka client commonly used in Python services.",
        },
        "rabbitmq": {
            "python_equivalent": "pika",
            "official_docs": "https://pika.readthedocs.io/en/stable/",
            "notes": "RabbitMQ client documentation for Python.",
        },
        "supabase": {
            "python_equivalent": "supabase-py",
            "official_docs": "https://supabase.com/docs/reference/python/introduction",
            "notes": "Official Python client reference for Supabase.",
        },
        "feign": {
            "python_equivalent": "httpx",
            "official_docs": "https://www.python-httpx.org/",
            "notes": "HTTP client equivalent for service-to-service calls.",
        },
        "webclient": {
            "python_equivalent": "httpx-async",
            "official_docs": "https://www.python-httpx.org/async/",
            "notes": "Async HTTP client patterns for reactive service calls.",
        },
        "resttemplate": {
            "python_equivalent": "httpx",
            "official_docs": "https://www.python-httpx.org/",
            "notes": "HTTP client equivalent for synchronous outbound calls.",
        },
        "openapi-swagger": {
            "python_equivalent": "fastapi-openapi",
            "official_docs": "https://fastapi.tiangolo.com/tutorial/metadata/",
            "notes": "OpenAPI and docs generation are built into FastAPI.",
        },
        "junit": {
            "python_equivalent": "pytest",
            "official_docs": "https://docs.pytest.org/en/stable/",
            "notes": "Primary Python testing framework equivalent.",
        },
        "docker": {
            "python_equivalent": "docker",
            "official_docs": "https://docs.docker.com/",
            "notes": "Containerization references remain directly relevant.",
        },
        "yaml": {
            "python_equivalent": "pydantic-settings",
            "official_docs": "https://docs.pydantic.dev/latest/concepts/pydantic_settings/",
            "notes": "Application configuration is often migrated to env/settings-driven config.",
        },
        "maven": {
            "python_equivalent": "pip",
            "official_docs": "https://pip.pypa.io/en/stable/",
            "notes": "Python package installation and dependency management baseline.",
        },
        "java-8": {
            "python_equivalent": "python-3-11",
            "official_docs": "https://docs.python.org/3.11/",
            "notes": "Recommended modern Python runtime target for the migrated backend.",
        },
        "apache-commons-lang": {
            "python_equivalent": "python-stdlib",
            "official_docs": "https://docs.python.org/3/library/",
            "notes": "Many utility helpers migrate to the Python standard library.",
        },
    }

    def __init__(
        self,
        *,
        search_service: SerperSearchService | None = None,
        mcp_research_service: MCPResearchService | None = None,
        enricher: DocsResearchLLMEnricher | None = None,
    ) -> None:
        self.search_service = search_service or SerperSearchService()
        self.mcp_research_service = mcp_research_service or MCPResearchService()
        self.enricher = enricher or DocsResearchLLMEnricher()

    def build_references(self, *, technologies: list[str], artifacts_dir: str) -> DocsResearchResult:
        """Create a docs-references artifact for the discovered technology list."""
        references: list[dict[str, str]] = []
        dynamic_candidates: list[dict[str, object]] = []

        for technology in technologies:
            static_reference = self._REFERENCE_MAP.get(technology)
            if static_reference and technology not in self._DYNAMIC_RESEARCH_TECHS:
                references.append(
                    {
                        "java_technology": technology,
                        "python_equivalent": static_reference["python_equivalent"],
                        "official_docs": static_reference["official_docs"],
                        "notes": static_reference["notes"],
                        "google_results_count": "0",
                        "mcp_results_count": "0",
                    }
                )
                continue

            query = self._build_query(technology, static_reference)
            google_results = self.search_service.search(query=query)
            mcp_results = self.mcp_research_service.search(query=query)
            dynamic_candidates.append(
                {
                    "java_technology": technology,
                    "static_reference": static_reference,
                    "google_results": google_results,
                    "mcp_results": mcp_results,
                }
            )

        for enriched in self.enricher.enrich_batch(candidates=dynamic_candidates):
            candidate = next(item for item in dynamic_candidates if item["java_technology"] == enriched["java_technology"])
            static_reference = candidate.get("static_reference")
            if not enriched.get("official_docs") and not static_reference:
                continue
            references.append(
                {
                    "java_technology": enriched["java_technology"],
                    "python_equivalent": enriched["python_equivalent"],
                    "official_docs": enriched["official_docs"],
                    "notes": enriched["notes"],
                    "google_results_count": str(len(candidate["google_results"])),
                    "mcp_results_count": str(len(candidate["mcp_results"])),
                }
            )

        artifact_dir = Path(artifacts_dir)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = artifact_dir / "06-integration-mapping.md"
        artifact_path.write_text(self._render_markdown(references), encoding="utf-8")
        return DocsResearchResult(references=references, artifact_path=artifact_path)

    def _build_query(self, technology: str, static_reference: dict[str, str] | None) -> str:
        if static_reference:
            return f"official python docs {static_reference['python_equivalent']} for {technology}"
        return f"official python docs equivalent for {technology}"

    def _render_markdown(self, references: list[dict[str, str]]) -> str:
        if not references:
            rows = "- No official Python-equivalent references were mapped yet."
        else:
            rows = "\n".join(
                (
                    f"## {item['java_technology']}\n"
                    f"- Python equivalent: {item['python_equivalent']}\n"
                    f"- Official docs: {item['official_docs']}\n"
                    f"- Notes: {item['notes']}\n"
                    f"- Google results used: {item['google_results_count']}\n"
                    f"- MCP results used: {item['mcp_results_count']}\n"
                )
                for item in references
            )
        return "# Integration Mapping\n\n" + rows + "\n"
