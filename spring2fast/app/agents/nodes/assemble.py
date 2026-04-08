"""Final assembly node — post-processes output and packages supporting artifacts."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import re
import shutil

from app.agents.generators.alembic_generator import AlembicGenerator
from app.agents.generators.docker_generator import DockerGenerator
from app.agents.generators.test_generator import TestGenerator
from app.agents.state import MigrationState


_PLACEHOLDER_PACKAGES = re.compile(r"\b(yourapp|myapp|your_app|my_app|application|project)\b")


def _sanitize_output_dir(output_dir: Path) -> int:
    """Replace placeholder package names in all generated .py files."""
    fixed = 0
    for py_file in output_dir.rglob("*.py"):
        try:
            original = py_file.read_text(encoding="utf-8", errors="ignore")
            cleaned = _PLACEHOLDER_PACKAGES.sub("app", original)
            if cleaned != original:
                py_file.write_text(cleaned, encoding="utf-8")
                fixed += 1
        except Exception:
            pass
    return fixed


def _write_if_missing(output_dir: Path, relative_path: str, content: str, generated: list[str]) -> None:
    file_path = output_dir / relative_path
    if file_path.exists():
        return
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")
    generated.append(relative_path)


def _generate_infrastructure_files(
    *,
    output_dir: Path,
    discovered_technologies: list[str],
    generated_files: list[str],
) -> list[str]:
    """Backfill core infra files that every runnable FastAPI app needs."""
    created: list[str] = []
    security_enabled = "spring-security" in discovered_technologies or "jwt" in discovered_technologies

    _write_if_missing(output_dir, "app/__init__.py", "", created)
    _write_if_missing(output_dir, "app/db/__init__.py", "", created)
    _write_if_missing(output_dir, "app/core/__init__.py", "", created)
    _write_if_missing(output_dir, "app/api/__init__.py", "", created)
    _write_if_missing(output_dir, "app/api/v1/__init__.py", "", created)
    _write_if_missing(output_dir, "app/api/v1/endpoints/__init__.py", "", created)
    _write_if_missing(
        output_dir,
        "app/db/base.py",
        '"""Declarative base for ORM models."""\n\nfrom sqlalchemy.orm import DeclarativeBase\n\n\nclass Base(DeclarativeBase):\n    pass\n',
        created,
    )
    _write_if_missing(
        output_dir,
        "app/db/session.py",
        (
            '"""Database engine and session dependency."""\n\n'
            "from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine\n\n"
            "from app.core.config import settings\n"
            "from app.db.base import Base\n\n"
            "engine = create_async_engine(settings.database_url)\n"
            "AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)\n\n"
            "async def get_db():\n"
            "    async with AsyncSessionLocal() as session:\n"
            "        yield session\n"
        ),
        created,
    )
    _write_if_missing(
        output_dir,
        "app/api/deps.py",
        '"""Shared API dependencies."""\n\nfrom app.db.session import get_db  # noqa: F401\n',
        created,
    )
    if security_enabled:
        _write_if_missing(
            output_dir,
            "app/core/security.py",
            (
                '"""JWT dependency stubs for migrated security flows."""\n\n'
                "from fastapi import Depends, HTTPException, status\n"
                "from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer\n\n"
                "try:\n"
                "    from jose import JWTError, jwt\n"
                "except ImportError:\n"
                "    JWTError = Exception\n"
                "    jwt = None\n\n"
                "from app.core.config import settings\n\n"
                "security = HTTPBearer(auto_error=False)\n\n"
                "async def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(security)) -> str:\n"
                "    if not credentials or jwt is None:\n"
                '        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=\"Unauthorized\")\n'
                "    try:\n"
                '        payload = jwt.decode(credentials.credentials, settings.secret_key, algorithms=[\"HS256\"])\n'
                "        return str(payload.get(\"sub\") or \"\")\n"
                "    except JWTError as exc:\n"
                '        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=\"Unauthorized\") from exc\n'
            ),
            created,
        )

    for item in created:
        if item not in generated_files:
            generated_files.append(item)
    return created


def assemble_node(state: MigrationState) -> MigrationState:
    """Post-process output, generate runnable project extras, and package as ZIP."""
    next_state = deepcopy(state)
    output_dir = Path(next_state["output_dir"])
    artifacts_dir = Path(next_state["artifacts_dir"])
    logs = list(next_state.get("logs", []))
    generated_files = list(next_state.get("generated_files", []))
    discovered_technologies = next_state.get("discovered_technologies", [])
    component_inventory = next_state.get("component_inventory") or next_state.get("metadata", {}).get("component_inventory", {})

    if output_dir.exists():
        fixed_count = _sanitize_output_dir(output_dir)
        if fixed_count:
            logs.append(f"Fixed placeholder imports in {fixed_count} files")

        infra_files = _generate_infrastructure_files(
            output_dir=output_dir,
            discovered_technologies=discovered_technologies,
            generated_files=generated_files,
        )
        if infra_files:
            logs.append(f"Generated infrastructure files: {', '.join(infra_files)}")

        docker_result = DockerGenerator().generate(
            output_dir=str(output_dir),
            discovered_technologies=discovered_technologies,
        )
        generated_files.extend(docker_result.generated_files)

        alembic_result = AlembicGenerator().generate(
            output_dir=str(output_dir),
            component_inventory=component_inventory,
            discovered_technologies=discovered_technologies,
        )
        generated_files.extend(alembic_result.generated_files)

        test_result = TestGenerator().generate(
            output_dir=str(output_dir),
            component_inventory=component_inventory,
        )
        generated_files.extend(test_result.generated_files)

        logs.append("Generated Docker, Alembic, and pytest scaffolding")

    zip_filename = f"fastapi_project_{next_state['job_id'][:8]}.zip"
    zip_path = artifacts_dir / zip_filename
    if output_dir.exists():
        shutil.make_archive(str(zip_path.with_suffix("")), "zip", str(output_dir))

    next_state["generated_files"] = sorted(set(generated_files))
    next_state["status"] = "completed"
    next_state["current_step"] = "Successfully migrated and packaged FastAPI project"
    next_state["progress_pct"] = 100
    next_state["metadata"] = {
        **next_state.get("metadata", {}),
        "output_zip": str(zip_path),
        "output_dir": str(output_dir),
    }
    logs.append(f"Generated {len(next_state['generated_files'])} files")
    logs.append(f"Packaged result into {zip_filename}")
    next_state["logs"] = logs
    return next_state
