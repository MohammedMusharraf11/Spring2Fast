"""Docker artifact generation for migrated projects."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class DockerGenerationResult:
    generated_files: list[str]


class DockerGenerator:
    """Generate Dockerfile and docker-compose for the assembled output."""

    def generate(self, *, output_dir: str, discovered_technologies: list[str]) -> DockerGenerationResult:
        output_root = Path(output_dir)
        generated: list[str] = []

        dockerfile = output_root / "Dockerfile"
        dockerfile.write_text(
            "\n".join(
                [
                    "FROM python:3.11-slim",
                    "WORKDIR /app",
                    "COPY requirements.txt .",
                    "RUN pip install --no-cache-dir -r requirements.txt",
                    "COPY . .",
                    'CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]',
                    "",
                ]
            ),
            encoding="utf-8",
        )
        generated.append("Dockerfile")

        compose_lines = [
            "services:",
            "  api:",
            "    build: .",
            '    ports: ["8000:8000"]',
            "    environment:",
        ]
        if "mysql" in discovered_technologies:
            compose_lines.append('      - DATABASE_URL=mysql+asyncmy://root:postgres@db:3306/app')
        else:
            compose_lines.append('      - DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/app')
        compose_lines.extend(
            [
                "    depends_on:",
                "      - db",
                "  db:",
            ]
        )
        if "mysql" in discovered_technologies:
            compose_lines.extend(
                [
                    "    image: mysql:8",
                    "    environment:",
                    "      MYSQL_ROOT_PASSWORD: postgres",
                    "      MYSQL_DATABASE: app",
                ]
            )
        else:
            compose_lines.extend(
                [
                    "    image: postgres:16-alpine",
                    "    environment:",
                    "      POSTGRES_PASSWORD: postgres",
                    "      POSTGRES_DB: app",
                ]
            )

        if "redis" in discovered_technologies:
            compose_lines.extend(
                [
                    "  redis:",
                    "    image: redis:7-alpine",
                    '    ports: ["6379:6379"]',
                ]
            )

        if "kafka" in discovered_technologies:
            compose_lines.extend(
                [
                    "  zookeeper:",
                    "    image: confluentinc/cp-zookeeper:7.5.0",
                    "    environment:",
                    "      ZOOKEEPER_CLIENT_PORT: 2181",
                    "  kafka:",
                    "    image: confluentinc/cp-kafka:7.5.0",
                    "    depends_on:",
                    "      - zookeeper",
                    "    environment:",
                    "      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181",
                    "      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092",
                    "      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1",
                ]
            )

        compose_path = output_root / "docker-compose.yml"
        compose_path.write_text("\n".join(compose_lines) + "\n", encoding="utf-8")
        generated.append("docker-compose.yml")

        return DockerGenerationResult(generated_files=generated)
