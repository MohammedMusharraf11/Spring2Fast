"""Alembic scaffold generation for migrated projects."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class AlembicGenerationResult:
    generated_files: list[str]


class AlembicGenerator:
    """Generate a minimal Alembic scaffold and initial migration."""

    def generate(
        self,
        *,
        output_dir: str,
        component_inventory: dict[str, list[dict]],
        discovered_technologies: list[str],
    ) -> AlembicGenerationResult:
        output_root = Path(output_dir)
        generated: list[str] = []
        alembic_dir = output_root / "alembic"
        versions_dir = alembic_dir / "versions"
        versions_dir.mkdir(parents=True, exist_ok=True)

        if "mysql" in discovered_technologies:
            fallback_url = "mysql+asyncmy://root:password@localhost:3306/app"
        elif "postgresql" in discovered_technologies or "spring-data-jpa" in discovered_technologies:
            fallback_url = "postgresql+asyncpg://postgres:password@localhost:5432/app"
        else:
            fallback_url = "sqlite:///./app.db"

        env_path = alembic_dir / "env.py"
        env_path.write_text(
            "\n".join(
                [
                    '"""Alembic environment for migrated project."""',
                    "",
                    "import os",
                    "from logging.config import fileConfig",
                    "from alembic import context",
                    "from sqlalchemy import engine_from_config, pool",
                    "",
                    "from app.core.config import settings",
                    "from app.db.base import Base",
                    "",
                    "config = context.config",
                    f'fallback_url = "{fallback_url}"',
                    'config.set_main_option("sqlalchemy.url", os.environ.get("DATABASE_URL", getattr(settings, "database_url", fallback_url) or fallback_url))',
                    "",
                    "if config.config_file_name is not None:",
                    "    fileConfig(config.config_file_name)",
                    "",
                    "target_metadata = Base.metadata",
                    "",
                    "def run_migrations_offline() -> None:",
                    '    context.configure(url=settings.database_url, target_metadata=target_metadata, literal_binds=True)',
                    "    with context.begin_transaction():",
                    "        context.run_migrations()",
                    "",
                    "def run_migrations_online() -> None:",
                    "    connectable = engine_from_config(",
                    "        config.get_section(config.config_ini_section) or {},",
                    '        prefix="sqlalchemy.",',
                    "        poolclass=pool.NullPool,",
                    "    )",
                    "    with connectable.connect() as connection:",
                    "        context.configure(connection=connection, target_metadata=target_metadata)",
                    "        with context.begin_transaction():",
                    "            context.run_migrations()",
                    "",
                    "if context.is_offline_mode():",
                    "    run_migrations_offline()",
                    "else:",
                    "    run_migrations_online()",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        generated.append("alembic/env.py")

        mako_path = alembic_dir / "script.py.mako"
        mako_path.write_text(
            "${message}\n\nrevision = ${repr(up_revision)}\ndown_revision = ${repr(down_revision)}\nbranch_labels = ${repr(branch_labels)}\ndepends_on = ${repr(depends_on)}\n\n\ndef upgrade():\n    pass\n\n\ndef downgrade():\n    pass\n",
            encoding="utf-8",
        )
        generated.append("alembic/script.py.mako")

        revision_path = versions_dir / "0001_initial.py"
        entity_names = [item.get("class_name", "Entity") for item in component_inventory.get("entities", [])]
        revision_path.write_text(
            "\n".join(
                [
                    '"""initial schema"""',
                    "",
                    "from alembic import op",
                    "import sqlalchemy as sa",
                    "",
                    "revision = '0001_initial'",
                    "down_revision = None",
                    "branch_labels = None",
                    "depends_on = None",
                    "",
                    "def upgrade() -> None:",
                    *(["    pass"] if not entity_names else [f"    # Create table for {name}" for name in entity_names]),
                    "",
                    "def downgrade() -> None:",
                    "    pass",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        generated.append("alembic/versions/0001_initial.py")

        ini_path = output_root / "alembic.ini"
        ini_path.write_text(
            "\n".join(
                [
                    "[alembic]",
                    "script_location = alembic",
                    "sqlalchemy.url = %(DATABASE_URL)s",
                    "",
                    "[loggers]",
                    "keys = root,sqlalchemy,alembic",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        generated.append("alembic.ini")

        return AlembicGenerationResult(generated_files=generated)
