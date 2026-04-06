"""Converter node wrappers — bridge between LangGraph nodes and converter agents.

Each function wraps a converter agent's async `convert()` call
and updates the migration state with the results.
"""

from __future__ import annotations

import asyncio
from copy import deepcopy
from typing import Any

from app.agents.state import MigrationState
from app.agents.converter_agents.model_converter import model_converter_agent
from app.agents.converter_agents.schema_converter import schema_converter_agent
from app.agents.converter_agents.repo_converter import repo_converter_agent
from app.agents.converter_agents.service_converter import service_converter_agent
from app.agents.converter_agents.controller_converter import controller_converter_agent
from app.agents.converter_agents.exception_converter import exception_converter_agent


async def _push_progress(state: MigrationState) -> None:
    """Push per-component progress to Supabase so the frontend stays live."""
    job_id = state.get("job_id")
    if not job_id:
        return
    try:
        from app.supabase_client import get_supabase
        completed = len(state.get("completed_conversions", []))
        failed = len(state.get("failed_conversions", []))
        remaining = len(state.get("conversion_queue", []))
        total = completed + failed + remaining
        # Migration phase spans 60–92% of overall progress
        pct = 60 + int(32 * (completed + failed) / max(total, 1))
        db = get_supabase()
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: db.table("migration_jobs").update({
                "status": "migrating",
                "current_step": state.get("current_step", "Converting components..."),
                "progress_pct": pct,
            }).eq("id", job_id).execute(),
        )
    except Exception:
        pass  # Non-critical — never crash the pipeline


async def _run_converter(state: MigrationState, agent: Any) -> MigrationState:
    """Shared logic: invoke a converter agent and capture its result in state."""
    next_state = deepcopy(state)
    current = next_state.get("current_conversion", {})
    if not current:
        return next_state

    component = current.get("component", {})

    # ── Throttle: only needed for Groq (30 RPM limit). Bedrock has no RPM cap. ──
    from app.core.llm import _bedrock_model as _check_bedrock
    using_bedrock = bool(
        __import__("app.config", fromlist=["settings"]).settings.bedrock_aws_access_key_id
    )
    if not using_bedrock:
        await asyncio.sleep(3.0)  # 3s = 20 req/min, safely under Groq's 30 RPM

    result = await agent.convert(
        component=component,
        input_dir=next_state.get("input_dir", ""),
        output_dir=next_state.get("output_dir", ""),
        contracts_dir=next_state.get("contracts_dir", ""),
        artifacts_dir=next_state.get("artifacts_dir", ""),
        discovered_technologies=next_state.get("discovered_technologies", []),
        existing_code=next_state.get("existing_generated_code", {}),
    )

    result_dict = result.to_dict()

    if result.passed:
        completed = next_state.get("completed_conversions", [])
        completed.append(result_dict)
        next_state["completed_conversions"] = completed
        next_state["generated_files"] = list(set(
            next_state.get("generated_files", []) + [result.output_path]
        ))
        next_state["logs"] = [
            *next_state.get("logs", []),
            f"OK {result.component_name} ({result.tier_used}, {result.attempts} attempts)",
        ]
    else:
        failed = next_state.get("failed_conversions", [])
        failed.append(result_dict)
        next_state["failed_conversions"] = failed
        next_state["logs"] = [
            *next_state.get("logs", []),
            f"FAIL {result.component_name}: {result.error}",
        ]

    next_state["current_conversion"] = None

    # ── Push live progress to Supabase after every converted component ──
    await _push_progress(next_state)

    return next_state


async def model_converter_node(state: MigrationState) -> MigrationState:
    """Convert a Java @Entity to a SQLAlchemy model."""
    return await _run_converter(state, model_converter_agent)


async def schema_converter_node(state: MigrationState) -> MigrationState:
    """Convert a Java DTO to a Pydantic schema."""
    return await _run_converter(state, schema_converter_agent)


async def repo_converter_node(state: MigrationState) -> MigrationState:
    """Convert a Spring Data Repository to SQLAlchemy repository."""
    return await _run_converter(state, repo_converter_agent)


async def service_converter_node(state: MigrationState) -> MigrationState:
    """Convert a Java @Service to a Python service class."""
    return await _run_converter(state, service_converter_agent)


async def controller_converter_node(state: MigrationState) -> MigrationState:
    """Convert a Java @RestController to a FastAPI router."""
    return await _run_converter(state, controller_converter_agent)


async def exception_converter_node(state: MigrationState) -> MigrationState:
    """Convert a Java @ControllerAdvice to FastAPI exception handlers."""
    return await _run_converter(state, exception_converter_agent)


def config_converter_node(state: MigrationState) -> MigrationState:
    """Generate ALL infrastructure/scaffold files — deterministic, no LLM.

    Generates: main.py, config.py, db/session.py, db/base.py, api/deps.py,
    api/v1/router.py, requirements.txt, .env.example, README.md,
    and all __init__.py package files.
    """
    import re
    from pathlib import Path

    next_state = deepcopy(state)
    output_dir = Path(next_state.get("output_dir", ""))
    techs = next_state.get("discovered_technologies", [])
    inventory = next_state.get("component_inventory", {})
    generated: list[str] = []

    def _write(rel_path: str, content: str) -> None:
        fp = output_dir / rel_path
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content, encoding="utf-8")
        generated.append(rel_path)

    def _to_snake(name: str) -> str:
        name = (name.removesuffix("Controller").removesuffix("Service")
                .removesuffix("ServiceImpl").removesuffix("Repository")
                .removesuffix("Entity").removesuffix("Impl"))
        return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()

    # ── main.py ──
    _write("app/main.py", (
        '"""FastAPI application entry point."""\n\n'
        "from fastapi import FastAPI\n"
        "from fastapi.middleware.cors import CORSMiddleware\n\n"
        "from app.api.v1.router import api_router\n"
        "from app.db.session import engine, Base\n\n\n"
        'app = FastAPI(title="Migrated FastAPI Backend")\n\n'
        "app.add_middleware(\n"
        "    CORSMiddleware,\n"
        '    allow_origins=["*"],\n'
        "    allow_credentials=True,\n"
        '    allow_methods=["*"],\n'
        '    allow_headers=["*"],\n'
        ")\n\n\n"
        "@app.on_event(\"startup\")\n"
        "async def startup():\n"
        "    async with engine.begin() as conn:\n"
        "        await conn.run_sync(Base.metadata.create_all)\n\n\n"
        'app.include_router(api_router, prefix="/api/v1")\n\n\n'
        '@app.get("/")\n'
        "async def root():\n"
        '    return {"message": "Migrated FastAPI backend"}\n'
    ))

    # ── db/base.py ──
    _write("app/db/base.py", (
        '"""Declarative Base for SQLAlchemy models."""\n\n'
        "from sqlalchemy.orm import DeclarativeBase\n\n\n"
        "class Base(DeclarativeBase):\n"
        '    """Base class for all ORM models."""\n'
        "    pass\n"
    ))

    # ── db/session.py ──
    db_url = '"sqlite+aiosqlite:///./app.db"'
    if "postgresql" in techs:
        db_url = '"postgresql+asyncpg://user:pass@localhost:5432/appdb"'
    elif "mysql" in techs:
        db_url = '"mysql+asyncmy://user:pass@localhost:3306/appdb"'

    _write("app/db/session.py", (
        '"""Database engine and session factory."""\n\n'
        "from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine\n\n"
        "from app.core.config import settings\n"
        "from app.db.base import Base\n\n\n"
        "engine = create_async_engine(settings.database_url, echo=False)\n\n"
        "async_session = async_sessionmaker(\n"
        "    engine, class_=AsyncSession, expire_on_commit=False,\n"
        ")\n\n\n"
        "async def get_db():\n"
        '    """Dependency that yields a database session."""\n'
        "    async with async_session() as session:\n"
        "        try:\n"
        "            yield session\n"
        "            await session.commit()\n"
        "        except Exception:\n"
        "            await session.rollback()\n"
        "            raise\n"
    ))

    # ── core/config.py ──
    config_fields = [
        '    app_name: str = "Migrated FastAPI Backend"',
        f"    database_url: str = {db_url}",
        '    secret_key: str = "change-me-to-a-secure-random-string"',
    ]
    if "redis" in techs:
        config_fields.append('    redis_url: str = "redis://localhost:6379/0"')
    if "kafka" in techs:
        config_fields.append('    kafka_bootstrap_servers: str = "localhost:9092"')

    _write("app/core/config.py", (
        '"""Application settings."""\n\n'
        "from pydantic_settings import BaseSettings, SettingsConfigDict\n\n\n"
        "class Settings(BaseSettings):\n"
        '    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")\n\n'
        + "\n".join(config_fields) + "\n\n\n"
        "settings = Settings()\n"
    ))

    # ── core/security.py ──
    if "spring-security" in techs or "jwt" in techs:
        _write("app/core/security.py", (
            '"""JWT authentication dependencies."""\n\n'
            "from fastapi import Depends, HTTPException, status\n"
            "from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials\n\n"
            "try:\n"
            "    from jose import jwt, JWTError\n"
            "except ImportError:\n"
            "    jwt = None\n"
            "    JWTError = Exception\n\n"
            "from app.core.config import settings\n\n"
            "security = HTTPBearer(auto_error=False)\n\n\n"
            "async def get_current_user(\n"
            "    credentials: HTTPAuthorizationCredentials | None = Depends(security),\n"
            ") -> str:\n"
            '    """Validate JWT and return user identifier."""\n'
            "    if not credentials:\n"
            '        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")\n'
            "    try:\n"
            "        payload = jwt.decode(\n"
            '            credentials.credentials, settings.secret_key, algorithms=["HS256"]\n'
            "        )\n"
            '        user_id: str | None = payload.get("sub")\n'
            "        if user_id is None:\n"
            '            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")\n'
            "        return user_id\n"
            "    except JWTError:\n"
            '        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")\n'
        ))

    # ── api/deps.py ──
    _write("app/api/deps.py", (
        '"""Shared API dependencies."""\n\n'
        "from app.db.session import get_db  # noqa: F401\n"
    ))

    # ── api/v1/router.py ── (auto-import all controller endpoints)
    controller_imports: list[str] = []
    controller_includes: list[str] = []
    for ctrl in inventory.get("controllers", []):
        name = ctrl.get("class_name", "")
        snake = _to_snake(name)
        controller_imports.append(
            f"from app.api.v1.endpoints.{snake} import router as {snake}_router"
        )
        # Extract base path from annotations if available
        prefix = f"/{snake.replace('_', '-')}"
        controller_includes.append(
            f'api_router.include_router({snake}_router, prefix="{prefix}", tags=["{snake}"])'
        )

    router_code = (
        '"""API v1 router — auto-generated from discovered controllers."""\n\n'
        "from fastapi import APIRouter\n\n"
    )
    if controller_imports:
        router_code += "\n".join(controller_imports) + "\n\n"
    router_code += "api_router = APIRouter()\n\n"
    if controller_includes:
        router_code += "\n".join(controller_includes) + "\n"
    else:
        router_code += "# No controllers discovered\n"

    _write("app/api/v1/router.py", router_code)

    # ── __init__.py for every package ──
    packages = [
        "app", "app/core", "app/db", "app/models", "app/schemas",
        "app/services", "app/repositories", "app/api", "app/api/v1",
        "app/api/v1/endpoints",
    ]
    for pkg in packages:
        init_path = output_dir / pkg / "__init__.py"
        if not init_path.exists():
            init_path.parent.mkdir(parents=True, exist_ok=True)
            init_path.write_text("", encoding="utf-8")
            generated.append(f"{pkg}/__init__.py")

    # ── requirements.txt ──
    reqs = [
        "fastapi", "uvicorn[standard]", "python-multipart",
        "pydantic", "pydantic-settings",
        "sqlalchemy", "aiosqlite",
    ]
    if "postgresql" in techs:
        reqs.extend(["asyncpg", "psycopg2-binary"])
    if "mysql" in techs:
        reqs.append("asyncmy")
    if "mongodb" in techs:
        reqs.extend(["motor", "beanie"])
    if "redis" in techs:
        reqs.append("redis[hiredis]")
    if "spring-security" in techs or "jwt" in techs:
        reqs.extend(["python-jose[cryptography]", "passlib[bcrypt]"])
    if "kafka" in techs:
        reqs.append("aiokafka")
    if "rabbitmq" in techs:
        reqs.append("aio-pika")
    if "supabase" in techs:
        reqs.append("supabase")

    _write("requirements.txt", "\n".join(sorted(set(reqs))) + "\n")

    # ── .env.example ──
    env_lines = [
        "# Application",
        'APP_NAME="Migrated FastAPI Backend"',
        "DATABASE_URL=" + db_url.strip('"'),
        'SECRET_KEY="change-me-to-a-secure-random-string"',
    ]
    if "redis" in techs:
        env_lines.append("REDIS_URL=redis://localhost:6379/0")
    _write(".env.example", "\n".join(env_lines) + "\n")

    # ── README.md ──
    _write("README.md", (
        "# Migrated FastAPI Backend\n\n"
        "Auto-generated by Spring2Fast.\n\n"
        "## Quick Start\n\n"
        "```bash\n"
        "pip install -r requirements.txt\n"
        "cp .env.example .env\n"
        "uvicorn app.main:app --reload\n"
        "```\n\n"
        f"## Technologies Detected\n\n{', '.join(techs) if techs else 'None'}\n"
    ))

    # ── Record results ──
    completed = next_state.get("completed_conversions", [])
    completed.append({
        "component_name": "ProjectConfig",
        "component_type": "config",
        "output_path": ", ".join(generated[:5]) + "...",
        "passed": True,
        "error": "",
        "attempts": 1,
        "tier_used": "deterministic",
    })
    next_state["completed_conversions"] = completed
    next_state["generated_files"] = list(set(
        next_state.get("generated_files", []) + generated
    ))
    next_state["current_conversion"] = None
    next_state["logs"] = [
        *next_state.get("logs", []),
        f"OK ProjectConfig: generated {len(generated)} infrastructure files",
    ]
    return next_state
