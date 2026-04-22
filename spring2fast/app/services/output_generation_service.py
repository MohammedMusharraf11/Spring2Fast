"""Artifact-driven FastAPI scaffold generation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import re
import shutil


@dataclass(slots=True)
class OutputGenerationResult:
    """Structured result for generated scaffold output."""

    generated_files: list[str]
    output_root: Path
    readme_path: Path


from app.services.llm_synthesis_service import LLMSynthesisService


class OutputGenerationService:
    """Generates a backend-only FastAPI project using LLM-driven deep synthesis."""

    def __init__(self, synthesis_service: LLMSynthesisService | None = None) -> None:
        self.synthesis_service = synthesis_service or LLMSynthesisService()

    async def generate_scaffold(
        self,
        *,
        output_dir: str,
        input_dir: str,
        target_files: list[str],
        implementation_steps: list[str],
        discovered_technologies: list[str],
        business_rules: list[str],
        source_url: str,
        docs_context: str = "",
        requested_chunk: str | None = None,
        component_inventory: dict[str, list[dict[str, Any]]] | None = None,
    ) -> OutputGenerationResult:
        output_root = Path(output_dir)
        # Only clean on the first pass (e.g., when requested_chunk is None or "models")
        if not requested_chunk or requested_chunk == "models":
            if output_root.exists():
                shutil.rmtree(output_root)
            output_root.mkdir(parents=True, exist_ok=True)

        component_inventory = component_inventory or {}
        generated_files: list[str] = []

        # Write planned scaffold files first.
        for relative_path in target_files:
            file_path = output_root / relative_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            content = self._render_file(
                relative_path=relative_path,
                discovered_technologies=discovered_technologies,
                business_rules=business_rules,
            )
            file_path.write_text(content, encoding="utf-8")
            generated_files.append(str(file_path.relative_to(output_root)))

        # If requested_chunk is provided, we only synthesize that specific architectural layer.
        if requested_chunk:
            generated_files.extend(
                await self._synthesize_chunk(
                    chunk_key=requested_chunk,
                    output_root=output_root,
                    input_root=Path(input_dir),
                    component_inventory=component_inventory,
                    business_rules=business_rules,
                    discovered_tech=discovered_technologies,
                    docs_context=docs_context,
                )
            )
        else:
            # Full run (scaffold + all components) - fallback for non-chunked legacy calls
            for chunk in ["models", "schemas", "repositories", "services", "controllers"]:
                generated_files.extend(
                    await self._synthesize_chunk(
                        chunk_key=chunk,
                        output_root=output_root,
                        input_root=Path(input_dir),
                        component_inventory=component_inventory,
                        business_rules=business_rules,
                        discovered_tech=discovered_technologies,
                        docs_context=docs_context,
                    )
                )

        # Regenerate the API router after controller modules exist.
        router_path = output_root / "app" / "api" / "v1" / "router.py"
        router_path.parent.mkdir(parents=True, exist_ok=True)
        router_path.write_text(
            self._render_api_router(component_inventory.get("controllers", [])),
            encoding="utf-8",
        )
        router_rel = str(router_path.relative_to(output_root))
        if router_rel not in generated_files:
            generated_files.append(router_rel)

        requirements_path = output_root / "requirements.txt"
        requirements_path.write_text(
            self._render_requirements(discovered_technologies),
            encoding="utf-8",
        )
        if "requirements.txt" not in generated_files:
            generated_files.append("requirements.txt")

        env_path = output_root / ".env.example"
        env_path.write_text(self._render_env_example(discovered_technologies), encoding="utf-8")
        if ".env.example" not in generated_files:
            generated_files.append(".env.example")

        readme_path = output_root / "README.md"
        readme_path.write_text(
            self._render_readme(
                implementation_steps=implementation_steps,
                discovered_technologies=discovered_technologies,
                source_url=source_url,
            ),
            encoding="utf-8",
        )
        if "README.md" not in generated_files:
            generated_files.append("README.md")

        return OutputGenerationResult(
            generated_files=sorted(set(generated_files)),
            output_root=output_root,
            readme_path=readme_path,
        )

    async def _synthesize_chunk(
        self,
        *,
        chunk_key: str,
        output_root: Path,
        input_root: Path,
        component_inventory: dict[str, list[dict[str, Any]]],
        business_rules: list[str],
        discovered_tech: list[str],
        docs_context: str,
    ) -> list[str]:
        generated: list[str] = []
        
        # Map logical chunks to inventory keys
        chunk_map = {
            "models": "entities",
            "schemas": "dtos",
            "repositories": "repositories",
            "services": "services",
            "controllers": "controllers",
        }
        module_suffix_map = {
            "models": "model",
            "schemas": "schema",
            "repositories": "repository",
            "services": "service",
            "controllers": "controller",
        }
        
        inventory_key = chunk_map.get(chunk_key)
        if not inventory_key:
            return []

        components = component_inventory.get(inventory_key, [])
        for component in components:
            class_name = str(component["class_name"])
            java_path = component.get("file_path")
            module_name = self._component_module_name(class_name, module_suffix_map.get(chunk_key, chunk_key))
            
            # Target output path
            if chunk_key == "controllers":
                file_path = output_root / "app" / "api" / "v1" / "endpoints" / f"{module_name}.py"
            else:
                file_path = output_root / "app" / chunk_key / f"{module_name}.py"
                
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Read Java source for deep synthesis
            java_source = self._get_java_source(input_root, str(java_path)) if java_path else ""
            
            # Deep synthesis vs template fallback
            if java_source and self.synthesis_service:
                content = await self.synthesis_service.synthesize_module(
                    module_type=chunk_key,
                    java_source=java_source,
                    docs_context=docs_context,
                    business_rules=business_rules,
                    discovered_tech=discovered_tech,
                )
            else:
                # Fallback to local templates if no source or LLM
                content = self._render_fallback(chunk_key, component, component_inventory, business_rules)
            
            file_path.write_text(content, encoding="utf-8")
            generated.append(str(file_path.relative_to(output_root)))

        return generated

    def _get_java_source(self, input_root: Path, java_path_rel: str) -> str:
        """Safely fetch Java source relative to input root."""
        try:
            full_path = input_root / java_path_rel
            if full_path.exists():
                return full_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            pass
        return ""

    def _render_fallback(self, chunk_key: str, component: dict, inventory: dict, rules: list[str]) -> str:
        """Legacy template fallback."""
        if chunk_key == "controllers": return self._render_controller_module(component, inventory)
        if chunk_key == "services": return self._render_service_module(component, rules, inventory)
        if chunk_key == "repositories": return self._render_repository_module(component, inventory)
        if chunk_key == "models": return self._render_entity_module(component)
        if chunk_key == "schemas": return self._render_dto_module(component)
        return "# Migration pending"

    def _render_file(
        self,
        *,
        relative_path: str,
        discovered_technologies: list[str],
        business_rules: list[str],
    ) -> str:
        if relative_path == "app/main.py":
            return (
                '"""Generated FastAPI application entry point."""\n\n'
                "from fastapi import FastAPI\n\n"
                "from app.api.v1.router import api_router\n\n"
                'app = FastAPI(title="Migrated FastAPI Backend")\n'
                'app.include_router(api_router, prefix="/api/v1")\n\n'
                '@app.get("/")\n'
                "async def root():\n"
                '    return {"message": "Migrated backend scaffold"}\n'
            )

        if relative_path.endswith("health.py"):
            return (
                '"""Generated health endpoint."""\n\n'
                "from fastapi import APIRouter\n\n"
                "router = APIRouter()\n\n"
                '@router.get("/health")\n'
                "async def health_check():\n"
                '    return {"status": "ok"}\n'
            )

        if relative_path.endswith("migration.py"):
            return (
                '"""Placeholder migration-related endpoints generated from plan."""\n\n'
                "from fastapi import APIRouter\n\n"
                "router = APIRouter()\n\n"
                '@router.get("/migration-info")\n'
                "async def migration_info():\n"
                '    return {"generated": True}\n'
            )

        if relative_path == "app/core/config.py":
            settings_fields = [
                '    app_name: str = "Migrated FastAPI Backend"',
                '    database_url: str = "sqlite:///./app.db"',
                '    secret_key: str = "change-me-to-a-secure-random-string"',
            ]
            if "redis" in discovered_technologies:
                settings_fields.append('    redis_url: str = "redis://localhost:6379/0"')
            if "kafka" in discovered_technologies:
                settings_fields.append('    kafka_bootstrap_servers: str = "localhost:9092"')
            if "rabbitmq" in discovered_technologies:
                settings_fields.append('    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"')
            if "supabase" in discovered_technologies:
                settings_fields.append('    supabase_url: str = "https://your-project.supabase.co"')
                settings_fields.append('    supabase_key: str = "your-anon-key"')
            fields_text = "\n".join(settings_fields)
            return (
                '"""Generated application settings."""\n\n'
                "from pydantic_settings import BaseSettings, SettingsConfigDict\n\n\n"
                "class Settings(BaseSettings):\n"
                '    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")\n\n'
                f"{fields_text}\n\n\n"
                "settings = Settings()\n"
            )

        if relative_path == "app/core/security.py":
            if "spring-security" in discovered_technologies or "jwt" in discovered_technologies:
                return (
                    '"""Security module migrated from Spring Security."""\n\n'
                    "from fastapi import Depends, HTTPException, status\n"
                    "from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials\n\n"
                    "try:\n"
                    "    from jose import jwt, JWTError\n"
                    "except ImportError:\n"
                    "    jwt = None  # python-jose not installed\n"
                    "    JWTError = Exception\n\n"
                    "from app.core.config import settings\n\n"
                    "security = HTTPBearer(auto_error=False)\n\n\n"
                    "async def get_current_user(\n"
                    "    credentials: HTTPAuthorizationCredentials | None = Depends(security),\n"
                    ") -> str:\n"
                    '    """Validate JWT token and return user identifier."""\n'
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
                    '        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")\n\n\n'
                    "def require_role(*roles: str):\n"
                    '    """Dependency factory for role-based access control."""\n'
                    "    async def role_checker(current_user: str = Depends(get_current_user)):\n"
                    "        # TODO: Implement role lookup from your user store\n"
                    "        return current_user\n"
                    "    return role_checker\n"
                )
            else:
                return (
                    '"""Security placeholders — no Spring Security detected."""\n\n\n'
                    "def require_authenticated_user():\n"
                    '    """Placeholder — implement authentication as needed."""\n'
                    "    return True\n"
                )

        if relative_path == "app/api/deps.py":
            return (
                '"""Shared API dependencies."""\n\n'
                "from app.core.security import require_authenticated_user\n\n"
                "__all__ = ['require_authenticated_user']\n"
            )

        if relative_path == "app/db/session.py":
            return (
                '"""Database session setup."""\n\n'
                "from sqlalchemy import create_engine\n"
                "from sqlalchemy.orm import sessionmaker\n"
                "from app.core.config import settings\n\n"
                "engine = create_engine(settings.database_url)\n"
                "SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)\n\n\n"
                "def get_db():\n"
                '    """FastAPI dependency that yields a database session."""\n'
                "    db = SessionLocal()\n"
                "    try:\n"
                "        yield db\n"
                "    finally:\n"
                "        db.close()\n"
            )

        if relative_path == "app/db/base.py":
            return (
                '"""SQLAlchemy declarative base."""\n\n'
                "from sqlalchemy.orm import DeclarativeBase\n\n"
                "class Base(DeclarativeBase):\n"
                "    pass\n"
            )

        if relative_path.endswith("__init__.py"):
            note = "generated package placeholder"
            if business_rules and ("services" in relative_path or "repositories" in relative_path):
                note = f"generated package placeholder with {len(business_rules)} business-rule hints available"
            return f'"""{note}."""\n'

        if relative_path == "Dockerfile":
            return (
                "FROM python:3.11-slim\n"
                "WORKDIR /app\n"
                "COPY requirements.txt ./\n"
                "RUN pip install -r requirements.txt\n"
                "COPY . .\n"
                'CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]\n'
            )



        return (
            '"""Generated placeholder module."""\n\n'
            "# TODO: implement this module from migration artifacts.\n"
        )

    def _render_api_router(self, controllers: list[dict[str, object]]) -> str:
        import_lines = ["from app.api.v1.endpoints.health import router as health_router"]
        include_lines = ["api_router.include_router(health_router)"]
        for controller in controllers:
            module_name = self._component_module_name(str(controller["class_name"]), "controller")
            import_lines.append(f"from app.api.v1.endpoints.{module_name} import router as {module_name}_router")
            include_lines.append(f"api_router.include_router({module_name}_router)")

        imports = "\n".join(sorted(set(import_lines)))
        includes = "\n".join(sorted(set(include_lines)))
        if imports:
            imports += "\n\n"
        if includes:
            includes += "\n"
        return (
            '"""Generated API router."""\n\n'
            "from fastapi import APIRouter\n\n"
            f"{imports}"
            "api_router = APIRouter()\n\n"
            f"{includes}"
        )

    def _render_controller_module(
        self,
        controller: dict[str, object],
        component_inventory: dict[str, list[dict[str, object]]],
    ) -> str:
        class_name = str(controller["class_name"])
        module_name = self._component_module_name(class_name, "controller")
        class_mappings = controller.get("request_mappings") or []
        method_details = controller.get("method_details") or []
        methods = controller.get("methods") or ["handle"]
        schema_classes = {
            str(item["class_name"]): self._component_module_name(str(item["class_name"]), "dto")
            for item in component_inventory.get("dtos", [])
        }
        base_path = self._extract_base_path(class_mappings)

        operation_lines: list[str] = []
        required_imports = {"APIRouter"}

        if method_details:
            iterable = method_details
        else:
            iterable = [{"name": name, "mapping_annotations": [], "parameters": []} for name in methods]

        for index, method in enumerate(iterable):
            method_name = str(method.get("name") or (methods[index] if index < len(methods) else f"handle_{index + 1}"))
            mapping_annotations = method.get("mapping_annotations") or []
            mapping_value = str(mapping_annotations[0]) if mapping_annotations else '@GetMapping("/")'
            http_method, path = self._parse_mapping(mapping_value)
            full_path = self._join_paths(base_path, path)
            handler_name = self._safe_identifier(method_name)
            signature_parts, body_hint, import_names = self._build_handler_signature(
                method.get("parameters") or [],
                schema_classes,
            )
            required_imports.update(import_names)
            signature = ", ".join([""] + signature_parts) if signature_parts else ""
            response_comment = ""
            if method.get("return_type"):
                response_comment = f"    # Original return type: {method['return_type']}\n"
            operation_lines.append(
                f'@router.{http_method}("{full_path}")\n'
                f"async def {handler_name}({signature.lstrip(', ')}):\n"
                f"{response_comment}"
                f'    return {{"source_controller": "{class_name}", "handler": "{handler_name}", "body_type": {body_hint}}}\n'
            )

        operations = "\n\n".join(operation_lines)
        imports = ", ".join(sorted(required_imports))
        schema_imports = []
        for class_name_key, module_name_key in sorted(schema_classes.items()):
            if any(class_name_key in str(param.get("type", "")) for method in iterable for param in method.get("parameters", [])):
                schema_imports.append(f"from app.schemas.{module_name_key} import {class_name_key}")
        schema_imports_text = ("\n".join(schema_imports) + "\n\n") if schema_imports else ""
        return (
            f'"""Generated router for {class_name}."""\n\n'
            f"from fastapi import {imports}\n"
            f"{schema_imports_text}\n"
            f'router = APIRouter(tags=["{module_name}"])\n\n'
            f"{operations}\n"
        )

    def _render_service_module(
        self,
        service: dict[str, object],
        business_rules: list[str],
        component_inventory: dict[str, list[dict[str, object]]],
    ) -> str:
        class_name = str(service["class_name"])
        methods = service.get("methods") or []
        class_rules = [rule for rule in business_rules if rule.startswith(f"{class_name}.")][:8]
        repository = self._find_related_component(class_name, component_inventory.get("repositories", []))
        repository_class = str(repository["class_name"]) if repository else None
        repository_module = self._component_module_name(repository_class, "repository") if repository_class else None
        method_blocks = []
        for method in methods[:12]:
            method_name = self._safe_identifier(str(method))
            if method_name == "__init__":
                continue
            matching_rules = [rule for rule in class_rules if f".{method_name}:" in rule]
            notes = "\n".join(f"        - {rule}" for rule in matching_rules) or "        - No extracted rule hints yet."
            method_body = self._render_service_method_body(method_name, repository_class, matching_rules)
            method_blocks.append(
                f"    def {method_name}(self, *args, **kwargs):\n"
                f'        """Migrated from {class_name}.{method_name}.\n\n{notes}\n        """\n'
                f"{method_body}\n"
            )
        if not method_blocks:
            method_blocks.append(
                "    def execute(self, *args, **kwargs):\n"
                "        raise NotImplementedError('Business logic migration pending')\n"
            )
        methods_text = "\n".join(method_blocks)
        repository_import = ""
        init_block = ""
        if repository_class and repository_module:
            repository_import = f"from app.repositories.{repository_module} import {repository_class}\n\n"
            init_block = (
                "    def __init__(self, repository=None):\n"
                f"        self.repository = repository or {repository_class}()\n\n"
            )
        return (
            f'"""Generated service module for {class_name}."""\n\n'
            f"{repository_import}"
            f"class {class_name}:\n"
            f"{init_block}"
            f"{methods_text}\n"
        )

    def _render_repository_module(
        self,
        repository: dict[str, object],
        component_inventory: dict[str, list[dict[str, object]]],
    ) -> str:
        class_name = str(repository["class_name"])
        methods = repository.get("methods") or []
        entity = self._find_related_component(class_name, component_inventory.get("entities", []))
        entity_class = str(entity["class_name"]) if entity else None
        entity_module = self._component_module_name(entity_class, "entity") if entity_class else None
        method_blocks = []
        for method in methods[:12]:
            method_name = self._safe_identifier(str(method))
            if method_name == "__init__":
                continue
            method_blocks.append(self._render_repository_method(method_name, class_name, entity_class))
        if not method_blocks:
            method_blocks.append(
                "    def get_session(self):\n"
                "        raise NotImplementedError('Repository migration pending')\n"
            )
        methods_text = "\n".join(method_blocks)
        import_lines = [
            "from sqlalchemy import delete, select",
            "from app.db.session import SessionLocal",
        ]
        if entity_class and entity_module:
            import_lines.append(f"from app.models.{entity_module} import {entity_class}")
        imports = "\n".join(import_lines)
        return (
            f'"""Generated repository module for {class_name}."""\n\n'
            f"{imports}\n\n"
            f"class {class_name}:\n"
            f"{methods_text}\n"
        )

    def _render_entity_module(self, entity: dict[str, object]) -> str:
        class_name = str(entity["class_name"])
        fields = entity.get("fields") or []
        imports = ["from sqlalchemy.orm import Mapped, mapped_column", "from app.db.base import Base"]
        field_lines = []
        for field in fields[:20]:
            field_name = self._safe_identifier(str(field["name"]))
            python_type = self._map_java_type_to_python(str(field["type"]))
            column_args = "primary_key=True" if field_name == "id" else "default=None"
            field_lines.append(
                f"    {field_name}: Mapped[{python_type} | None] = mapped_column({column_args})"
            )
        if not field_lines:
            field_lines.append("    # TODO: infer columns, relationships, and constraints from the Java entity.")
            field_lines.append("    pass")
        return (
            f'"""Generated SQLAlchemy model placeholder for {class_name}."""\n\n'
            + "\n".join(imports)
            + "\n\n"
            f"class {class_name}(Base):\n"
            f'    __tablename__ = "{self._pluralize(self._component_module_name(class_name, "entity"))}"\n'
            + "\n".join(field_lines)
            + "\n"
        )

    def _render_dto_module(self, dto: dict[str, object]) -> str:
        class_name = str(dto["class_name"])
        fields = dto.get("fields") or []
        field_lines = []
        for field in fields[:20]:
            field_name = self._safe_identifier(str(field["name"]))
            python_type = self._map_java_type_to_python(str(field["type"]))
            is_required = any(
                marker in annotation
                for annotation in field.get("annotations", [])
                for marker in ("@NotNull", "@NotBlank", "@NotEmpty")
            )
            default_suffix = "" if is_required else " = None"
            field_lines.append(f"    {field_name}: {python_type} | None{default_suffix}")
        if not field_lines:
            field_lines.append("    # TODO: infer request/response fields and validation rules from the Java DTO.")
            field_lines.append("    pass")
        return (
            f'"""Generated Pydantic schema placeholder for {class_name}."""\n\n'
            "from pydantic import BaseModel\n\n"
            f"class {class_name}(BaseModel):\n"
            + "\n".join(field_lines)
            + "\n"
        )

    def _render_exception_module(self, handlers: list[dict[str, object]]) -> str:
        class_names = ", ".join(str(item["class_name"]) for item in handlers)
        return (
            '"""Generated exception handlers from Spring advice components."""\n\n'
            "from fastapi import FastAPI, Request\n"
            "from fastapi.responses import JSONResponse\n\n"
            f"# Source advice classes: {class_names}\n\n"
            "def register_exception_handlers(app: FastAPI) -> None:\n"
            "    @app.exception_handler(Exception)\n"
            "    async def generic_exception_handler(request: Request, exc: Exception):\n"
            '        return JSONResponse(status_code=500, content={"detail": str(exc)})\n'
        )

    def _parse_mapping(self, mapping: str) -> tuple[str, str]:
        if mapping.startswith("@GetMapping"):
            return "get", self._extract_path(mapping)
        if mapping.startswith("@PostMapping"):
            return "post", self._extract_path(mapping)
        if mapping.startswith("@PutMapping"):
            return "put", self._extract_path(mapping)
        if mapping.startswith("@DeleteMapping"):
            return "delete", self._extract_path(mapping)
        if mapping.startswith("@RequestMapping"):
            return "get", self._extract_path(mapping)
        return "get", "/"

    def _extract_path(self, mapping: str) -> str:
        match = re.search(r'"/([^"]*)"', mapping)
        if not match:
            return "/"
        path = "/" + match.group(1).lstrip("/")
        return path or "/"

    def _extract_base_path(self, mappings: list[object]) -> str:
        for mapping in mappings:
            mapping_text = str(mapping)
            if mapping_text.startswith("@RequestMapping"):
                return self._extract_path(mapping_text)
        return ""

    def _join_paths(self, base_path: str, method_path: str) -> str:
        if not base_path:
            return method_path
        if method_path == "/":
            return base_path
        return "/" + "/".join(part.strip("/") for part in (base_path, method_path) if part).strip("/")

    def _build_handler_signature(
        self,
        parameters: list[object],
        schema_classes: dict[str, str],
    ) -> tuple[list[str], str, set[str]]:
        signature_parts: list[str] = []
        imports: set[str] = set()
        body_hint = '"none"'
        for parameter in parameters:
            param = dict(parameter)
            name = self._safe_identifier(str(param.get("name", "payload")))
            java_type = str(param.get("type", "Object"))
            annotations = [str(item) for item in param.get("annotations", [])]
            python_type = self._map_java_type_to_python(java_type)
            schema_type = next((schema for schema in schema_classes if schema in java_type), None)
            if schema_type:
                python_type = schema_type
            if any("@PathVariable" in annotation for annotation in annotations):
                imports.add("Path")
                signature_parts.append(f"{name}: {python_type} = Path(...)")
                continue
            if any("@RequestParam" in annotation for annotation in annotations):
                imports.add("Query")
                signature_parts.append(f"{name}: {python_type} | None = Query(default=None)")
                continue
            if any("@RequestHeader" in annotation for annotation in annotations):
                imports.add("Header")
                signature_parts.append(f"{name}: {python_type} | None = Header(default=None)")
                continue
            if any("@RequestBody" in annotation for annotation in annotations):
                if not schema_type:
                    imports.add("Body")
                    signature_parts.append(f"{name}: dict = Body(...)")
                    body_hint = '"dict"'
                else:
                    signature_parts.append(f"{name}: {python_type}")
                    body_hint = f'"{python_type}"'
                continue
            signature_parts.append(f"{name}: {python_type} | None = None")
        return signature_parts, body_hint, imports

    def _component_module_name(self, class_name: str, suffix: str) -> str:
        base = (
            class_name.removesuffix("Controller")
            .removesuffix("Service")
            .removesuffix("Repository")
            .removesuffix("ExceptionHandler")
            .removesuffix("Entity")
        )
        snake = re.sub(r"(?<!^)(?=[A-Z])", "_", base).lower()
        if not snake:
            snake = class_name.lower()
        if suffix == "controller":
            return snake
        if suffix == "service":
            return f"{snake}_service"
        if suffix == "repository":
            return f"{snake}_repository"
        return snake

    def _safe_identifier(self, name: str) -> str:
        identifier = re.sub(r"[^0-9a-zA-Z_]", "_", name)
        if identifier and identifier[0].isdigit():
            identifier = f"method_{identifier}"
        return identifier or "handler"

    def _map_java_type_to_python(self, java_type: str) -> str:
        normalized = java_type.strip().split(".")[-1]
        normalized = normalized.replace("[]", "")
        mapping = {
            "String": "str",
            "Long": "int",
            "Integer": "int",
            "int": "int",
            "long": "int",
            "Double": "float",
            "double": "float",
            "Float": "float",
            "float": "float",
            "Boolean": "bool",
            "boolean": "bool",
            "BigDecimal": "float",
            "LocalDate": "str",
            "LocalDateTime": "str",
            "Date": "str",
            "UUID": "str",
        }
        if normalized.startswith("List<") or normalized.startswith("Set<"):
            return "list"
        return mapping.get(normalized, "str")

    def _pluralize(self, value: str) -> str:
        if value.endswith("s"):
            return value
        if value.endswith("y") and len(value) > 1 and value[-2] not in "aeiou":
            return value[:-1] + "ies"
        return value + "s"

    def _find_related_component(
        self,
        class_name: str,
        components: list[dict[str, object]],
    ) -> dict[str, object] | None:
        base_name = self._base_component_name(class_name)
        for component in components:
            candidate = str(component["class_name"])
            if self._base_component_name(candidate) == base_name:
                return component
        return None

    def _base_component_name(self, class_name: str) -> str:
        return (
            class_name.removesuffix("Controller")
            .removesuffix("Service")
            .removesuffix("Repository")
            .removesuffix("ExceptionHandler")
            .removesuffix("Entity")
            .removesuffix("Dto")
            .removesuffix("DTO")
            .removesuffix("Request")
            .removesuffix("Response")
        )

    def _render_service_method_body(self, method_name: str, repository_class: str | None, matching_rules: list[str] | None = None) -> str:
        if not repository_class:
            return "        raise NotImplementedError('Business logic migration pending')"
            
        matching_rules = matching_rules or []
        rules_text = " ".join(matching_rules).lower()
        
        # Deep synthesis: infer logic directly from business rules if present
        if "persists data" in rules_text:
            return "        return self.repository.save(*args, **kwargs)"
        if "queries existing data" in rules_text:
            if "byid" in method_name.lower():
                return "        return self.repository.findById(*args, **kwargs)"
            return "        return self.repository.findAll(*args, **kwargs)"
        if "deletes data" in rules_text:
            return "        return self.repository.deleteById(*args, **kwargs)"

        lowered = method_name.lower()
        if lowered.startswith(("get", "find")):
            return "        return self.repository.findById(*args, **kwargs)"
        if lowered.startswith(("list", "fetch", "load")):
            return "        return self.repository.findAll(*args, **kwargs)"
        if lowered.startswith(("save", "create", "add", "update")):
            return "        return self.repository.save(*args, **kwargs)"
        if lowered.startswith(("delete", "remove")):
            return "        return self.repository.deleteById(*args, **kwargs)"
        if lowered.startswith(("exists", "has")):
            return "        return self.repository.exists(*args, **kwargs)"
        return "        raise NotImplementedError('Business logic migration pending')"

    def _render_repository_method(
        self,
        method_name: str,
        class_name: str,
        entity_class: str | None,
    ) -> str:
        if not entity_class:
            return (
                f"    def {method_name}(self, *args, **kwargs):\n"
                f'        """Migrated from {class_name}.{method_name}."""\n'
                "        raise NotImplementedError('Repository migration pending')\n"
            )

        lowered = method_name.lower()
        if lowered == "findbyid":
            return (
                "    def findById(self, id):\n"
                f'        """Migrated from {class_name}.findById."""\n'
                "        with SessionLocal() as session:\n"
                f"            statement = select({entity_class}).where({entity_class}.id == id)\n"
                "            return session.execute(statement).scalar_one_or_none()\n"
            )
        if lowered == "findall":
            return (
                "    def findAll(self):\n"
                f'        """Migrated from {class_name}.findAll."""\n'
                "        with SessionLocal() as session:\n"
                f"            statement = select({entity_class})\n"
                "            return list(session.execute(statement).scalars().all())\n"
            )
        if lowered == "save":
            return (
                "    def save(self, entity):\n"
                f'        """Migrated from {class_name}.save."""\n'
                "        with SessionLocal() as session:\n"
                "            session.add(entity)\n"
                "            session.commit()\n"
                "            session.refresh(entity)\n"
                "            return entity\n"
            )
        if lowered == "deletebyid":
            return (
                "    def deleteById(self, id):\n"
                f'        """Migrated from {class_name}.deleteById."""\n'
                "        with SessionLocal() as session:\n"
                f"            statement = delete({entity_class}).where({entity_class}.id == id)\n"
                "            result = session.execute(statement)\n"
                "            session.commit()\n"
                "            return result.rowcount or 0\n"
            )
        if lowered.startswith("findby"):
            field_name = self._java_query_field_to_python(method_name[6:])
            return (
                f"    def {method_name}(self, value):\n"
                f'        """Migrated from {class_name}.{method_name}."""\n'
                "        with SessionLocal() as session:\n"
                f"            statement = select({entity_class}).where({entity_class}.{field_name} == value)\n"
                "            return session.execute(statement).scalar_one_or_none()\n"
            )
        if lowered.startswith("existsby"):
            field_name = self._java_query_field_to_python(method_name[8:])
            return (
                f"    def {method_name}(self, value):\n"
                f'        """Migrated from {class_name}.{method_name}."""\n'
                "        with SessionLocal() as session:\n"
                f"            statement = select({entity_class}).where({entity_class}.{field_name} == value)\n"
                "            return session.execute(statement).scalar_one_or_none() is not None\n"
            )
        return (
            f"    def {method_name}(self, *args, **kwargs):\n"
            f'        """Migrated from {class_name}.{method_name}."""\n'
            "        raise NotImplementedError('Repository migration pending')\n"
        )

    def _java_query_field_to_python(self, value: str) -> str:
        if not value:
            return "id"
        normalized = value.split("And")[0].split("Or")[0]
        return self._safe_identifier(normalized[:1].lower() + normalized[1:])

    # ── Full technology → Python requirements mapping ──
    TECH_TO_REQUIREMENTS: dict[str, list[str]] = {
        "spring-data-jpa": ["sqlalchemy>=2.0", "alembic"],
        "hibernate": ["sqlalchemy>=2.0", "alembic"],
        "postgresql": ["asyncpg", "psycopg2-binary"],
        "mysql": ["pymysql"],
        "mongodb": ["motor", "pymongo"],
        "redis": ["redis>=5.0"],
        "kafka": ["aiokafka"],
        "rabbitmq": ["aio-pika"],
        "spring-security": ["python-jose[cryptography]", "passlib[bcrypt]"],
        "jwt": ["python-jose[cryptography]"],
        "bcrypt": ["passlib[bcrypt]"],
        "feign": ["httpx"],
        "webclient": ["httpx"],
        "resttemplate": ["httpx"],
        "supabase": ["supabase"],
        "aws": ["boto3"],
        "gcp": ["google-cloud-storage"],
        "azure": ["azure-storage-blob"],
    }

    def _render_requirements(self, discovered_technologies: list[str]) -> str:
        lines = [
            "fastapi",
            "uvicorn[standard]",
            "pydantic>=2.0",
            "pydantic-settings",
            "python-dotenv",
        ]
        seen: set[str] = set(lines)
        for tech in discovered_technologies:
            for req in self.TECH_TO_REQUIREMENTS.get(tech, []):
                if req not in seen:
                    seen.add(req)
                    lines.append(req)
        # Always include httpx for modern HTTP client support
        if "httpx" not in seen:
            lines.append("httpx")
        # Testing
        lines.extend(["\n# Testing", "pytest", "pytest-asyncio"])
        return "\n".join(lines) + "\n"

    def _render_env_example(self, discovered_technologies: list[str]) -> str:
        if "postgresql" in discovered_technologies:
            database_url = "postgresql+asyncpg://user:password@localhost:5432/myapp"
        elif "mysql" in discovered_technologies:
            database_url = "mysql+pymysql://user:password@localhost:3306/myapp"
        elif "mongodb" in discovered_technologies:
            database_url = "mongodb://localhost:27017/myapp"
        else:
            database_url = "sqlite:///./app.db"
        lines = [
            "# Application",
            "APP_NAME=Migrated FastAPI Backend",
            "",
            "# Database",
            f"DATABASE_URL={database_url}",
            "",
            "# Security",
            "SECRET_KEY=change-me-to-a-secure-random-string",
        ]
        if "redis" in discovered_technologies:
            lines.extend(["", "# Redis", "REDIS_URL=redis://localhost:6379/0"])
        if "kafka" in discovered_technologies:
            lines.extend(["", "# Kafka", "KAFKA_BOOTSTRAP_SERVERS=localhost:9092"])
        if "rabbitmq" in discovered_technologies:
            lines.extend(["", "# RabbitMQ", "RABBITMQ_URL=amqp://guest:guest@localhost:5672/"])
        if "supabase" in discovered_technologies:
            lines.extend(["", "# Supabase", "SUPABASE_URL=https://your-project.supabase.co", "SUPABASE_KEY=your-anon-key"])
        return "\n".join(lines) + "\n"

    def _render_readme(
        self,
        *,
        implementation_steps: list[str],
        discovered_technologies: list[str],
        source_url: str,
    ) -> str:
        tech_text = "\n".join(f"- {tech}" for tech in discovered_technologies) or "- none detected"
        step_text = "\n".join(f"- {step}" for step in implementation_steps) or "- none"
        return (
            "# Generated FastAPI Scaffold\n\n"
            f"- Source repository: {source_url}\n\n"
            "## Detected Backend Technologies\n"
            f"{tech_text}\n\n"
            "## Planned Migration Steps\n"
            f"{step_text}\n\n"
            "## Notes\n"
            "- This scaffold is backend-only and intentionally excludes Spring MVC templates or frontend assets.\n"
            "- Business rules and integration mappings should drive the next code generation stage.\n"
        )
