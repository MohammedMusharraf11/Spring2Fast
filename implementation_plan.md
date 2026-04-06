# Spring2Fast — Road to 100% Migration Fidelity

> This plan takes the backend from **~58% → 100%** migration readiness.  
> Every task lists the **exact file**, **what to build**, and **the best approach**.

---

## Phase 0 — Critical Bug Fixes (Do First)

> [!CAUTION]
> These are runtime crashers or silent data corruption. Fix before anything else.

### 0.1 — Fix Missing `Any` Import

**File:** `app/services/output_generation_service.py`

```python
# Line 1-8: Add the missing import
from typing import Any
```

---

### 0.2 — Remove Hardcoded `foodfrenzy` Database Name

**File:** `app/services/output_generation_service.py`

**Problem:** Lines 280 and 840 hardcode `foodfrenzy` and `mysql` credentials.

**Fix:** Generate dynamic DB URLs from the actual project metadata:

```python
def _render_env_example(self, discovered_technologies: list[str], project_name: str = "app") -> str:
    if "postgresql" in discovered_technologies:
        database_url = f"postgresql+asyncpg://user:password@localhost:5432/{project_name}"
    elif "mysql" in discovered_technologies:
        database_url = f"mysql+pymysql://user:password@localhost:3306/{project_name}"
    elif "mongodb" in discovered_technologies:
        database_url = f"mongodb://localhost:27017/{project_name}"
    else:
        database_url = "sqlite:///./app.db"
    return (
        f"APP_NAME={project_name}\n"
        f"DATABASE_URL={database_url}\n"
        "SECRET_KEY=change-me-to-a-secure-random-string\n"
    )
```

Do the same for `_render_file` case `app/db/session.py` — derive the URL from `.env` via `pydantic-settings`, never hardcode it.

---

### 0.3 — Fix Orchestrator Conditional Edge Crash

**File:** `app/services/migration_orchestrator.py`

**Problem:** Line 111 does `current = self.graph.edges[current]` which crashes when the edge is a `callable` (conditional edge from `validate`).

**Fix:**

```python
edge_val = self.graph.edges.get(current, "__end__")
if callable(edge_val):
    condition_result = edge_val(next_state)
    routing_map = self.graph.conditional_targets.get(current, {})
    current = routing_map.get(condition_result, condition_result)
else:
    current = edge_val
```

---

### 0.4 — Fix LLM Configuration

**File:** `app/core/llm.py`

**Changes:**
1. Set `temperature=0.1` (not `1`) for deterministic code generation
2. Set `max_tokens=16384` (not `1024`) so large classes don't truncate
3. Uncomment the Gemini and OpenAI providers
4. Implement a priority fallback chain: Groq → Gemini → OpenAI → None

```python
def get_chat_model() -> BaseChatModel | None:
    provider = settings.llm_provider.lower()

    # Priority 1: Groq (fastest, free tier)
    if provider in {"auto", "groq"} and settings.groq_api_key:
        from langchain_groq import ChatGroq
        return ChatGroq(
            model=settings.llm_model or "meta-llama/llama-4-scout-17b-16e-instruct",
            temperature=0.1,
            max_tokens=16384,
            api_key=settings.groq_api_key,
        )

    # Priority 2: Google Gemini
    if provider in {"auto", "google", "gemini"} and settings.google_api_key:
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=settings.llm_model or "gemini-2.0-flash",
            google_api_key=settings.google_api_key,
            temperature=0.1,
        )

    # Priority 3: OpenAI
    if provider in {"auto", "openai"} and settings.openai_api_key:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=settings.llm_model or "gpt-4o-mini",
            api_key=settings.openai_api_key,
            temperature=0.1,
        )

    return None
```

---

## Phase 1 — Real Java AST Parsing

> Replace regex-only parsing with `javalang` AST for deterministic, accurate extraction.

### 1.1 — Build a `JavaASTParser` Utility

**New file:** `app/services/java_ast_parser.py`

**What it does:** Wraps `javalang` to extract structured IR from any `.java` file.

```python
import javalang

class JavaASTParser:
    """Deterministic Java source parser using javalang AST."""

    def parse_file(self, source: str) -> dict:
        tree = javalang.parse.parse(source)
        return {
            "package": tree.package.name if tree.package else None,
            "imports": [imp.path for imp in tree.imports],
            "classes": [self._parse_class(cls) for _, cls in tree.filter(javalang.tree.ClassDeclaration)],
            "interfaces": [self._parse_interface(iface) for _, iface in tree.filter(javalang.tree.InterfaceDeclaration)],
            "enums": [self._parse_enum(enum) for _, enum in tree.filter(javalang.tree.EnumDeclaration)],
        }

    def _parse_class(self, cls) -> dict:
        return {
            "name": cls.name,
            "annotations": [self._parse_annotation(a) for a in (cls.annotations or [])],
            "extends": cls.extends.name if cls.extends else None,
            "implements": [impl.name for impl in (cls.implements or [])],
            "fields": [self._parse_field(f) for f in (cls.fields or [])],
            "methods": [self._parse_method(m) for m in (cls.methods or [])],
            "constructors": [self._parse_method(c) for c in (cls.constructors or [])],
        }

    def _parse_annotation(self, annotation) -> dict:
        return {
            "name": annotation.name,
            "arguments": {
                elem.name: elem.value.value if hasattr(elem.value, 'value') else str(elem.value)
                for elem in (annotation.element or [])
                if hasattr(elem, 'name')
            } if annotation.element else {},
        }

    def _parse_field(self, field) -> dict:
        return {
            "name": field.declarators[0].name if field.declarators else "unknown",
            "type": self._type_to_string(field.type),
            "annotations": [self._parse_annotation(a) for a in (field.annotations or [])],
            "modifiers": list(field.modifiers or []),
        }

    def _parse_method(self, method) -> dict:
        return {
            "name": method.name,
            "return_type": self._type_to_string(method.return_type) if hasattr(method, 'return_type') and method.return_type else "void",
            "parameters": [
                {
                    "name": p.name,
                    "type": self._type_to_string(p.type),
                    "annotations": [self._parse_annotation(a) for a in (p.annotations or [])],
                }
                for p in (method.parameters or [])
            ],
            "annotations": [self._parse_annotation(a) for a in (method.annotations or [])],
            "modifiers": list(method.modifiers or []),
            "body_source_lines": len(method.body) if method.body else 0,
        }

    def _type_to_string(self, type_node) -> str:
        if type_node is None:
            return "void"
        name = type_node.name
        if hasattr(type_node, 'arguments') and type_node.arguments:
            args = ", ".join(self._type_to_string(a) for a in type_node.arguments if hasattr(a, 'name'))
            return f"{name}<{args}>"
        if hasattr(type_node, 'dimensions') and type_node.dimensions:
            return f"{name}[]"
        return name
```

**Fallback:** If `javalang.parse.parse()` throws (it fails on some Java 17+ syntax), fall back to the existing regex parser. Never lose data.

---

### 1.2 — Integrate AST Parser into Component Discovery

**File:** `app/services/component_discovery_service.py`

Replace the regex-based `_extract_structure` with `JavaASTParser.parse_file()`. Keep regex as fallback:

```python
def _extract_component(self, file_path, text):
    try:
        parsed = self.ast_parser.parse_file(text)
        # Use structured AST data
        return self._from_ast(parsed, file_path)
    except Exception:
        # Fallback to regex
        return self._from_regex(file_path, text)
```

---

### 1.3 — Extract Full Method Bodies for LLM Context

**New addition to `JavaASTParser`:** Extract the **raw source** of each method body (not just the method count). This is critical — the LLM needs to see the actual Java logic.

```python
def extract_method_bodies(self, source: str) -> dict[str, str]:
    """Return {method_name: raw_java_source} for every method."""
    # Use line numbers from javalang nodes to slice the original source
    ...
```

This feeds directly into the LLM synthesis prompt as code-to-translate.

---

### 1.4 — Build Proper `IntermediateRepresentation` Dataclass

**New file:** `app/agents/ir.py` (referenced in README but never created)

```python
@dataclass
class EntityIR:
    name: str
    table_name: str
    package: str
    fields: list[FieldIR]
    relationships: list[RelationshipIR]

@dataclass
class ControllerIR:
    name: str
    base_path: str
    endpoints: list[EndpointIR]
    dependencies: list[str]

@dataclass
class ServiceIR:
    name: str
    methods: list[MethodIR]
    dependencies: list[str]  # injected via @Autowired
    transactions: list[str]  # methods annotated @Transactional

@dataclass
class IntermediateRepresentation:
    project_metadata: ProjectMetadata
    entities: list[EntityIR]
    controllers: list[ControllerIR]
    services: list[ServiceIR]
    repositories: list[RepositoryIR]
    configurations: list[ConfigIR]
    security: SecurityIR | None
    dependencies: DependencyMap
```

This typed IR replaces the loose `dict[str, list[dict]]` currently passing through the pipeline. Every downstream node benefits from typed access.

---

## Phase 2 — Per-Service Business Logic Contracts

> Replace the flat rules list with structured `.md` contract files per service.

### 2.1 — Rewrite `BusinessLogicService` to Emit Contracts

**File:** `app/services/business_logic_service.py`

**New behavior:** For each `@Service` class, generate a structured `.md` contract file:

```
workspace/{job_id}/contracts/
├── services/
│   ├── user_service.md
│   ├── order_service.md
│   └── payment_service.md
├── models/
│   ├── user_entity.md
│   └── order_entity.md
├── api/
│   ├── user_endpoints.md
│   └── order_endpoints.md
└── integrations/
    ├── kafka_events.md
    └── redis_cache.md
```

**Each contract file follows this template:**

```markdown
# {ClassName} — Business Logic Contract

## Methods

### {methodName}
- **Purpose:** {LLM-summarized purpose}
- **Input validation:** {extracted from @Valid, if-checks, @NotNull}
- **Business rules:**
  1. {rule extracted from if-else branches}
  2. {rule extracted from exception throws}
- **Side effects:** {email sends, event publishing, cache invalidation}
- **Error conditions:**
  | Condition | Exception | HTTP Status |
  |-----------|-----------|-------------|
  | {condition} | {ExceptionClass} | {status} |

## Dependencies
- {RepositoryClass} (database access)
- {OtherServiceClass} (business delegation)

## Annotations
- @Transactional on: {method list}
- @Cacheable on: {method list}
- @Async on: {method list}
```

**How to extract:**
1. Use `JavaASTParser` to get method signatures, annotations, parameters
2. Use regex patterns for `if/throw/save/delete/send` (existing logic)
3. Use LLM enricher to summarize the Java method body into structured contract sections
4. Write one `.md` per class

---

### 2.2 — Add `contracts_dir` to `MigrationState`

**File:** `app/agents/state.py`

```python
class MigrationState(TypedDict):
    ...
    contracts_dir: NotRequired[str]           # workspace/{job_id}/contracts/
    business_logic_contracts: NotRequired[list[dict]]  # [{contract_path, source_class, type}]
```

---

### 2.3 — Feed Contracts into Migration + Validation

**LLM Synthesis (Phase 3):** Each synthesis prompt includes the relevant `.md` contract.

**Validation (Phase 4):** LLM-as-judge checks generated code against each contract.

---

## Phase 3 — LLM Synthesis Overhaul

> The single most impactful change. Transform from a generic prompt to a specialized, context-rich synthesis engine.

### 3.1 — Create Per-Layer Prompt Templates

**New directory:** `app/agents/prompts/` — one `.md` template per layer type.

#### `prompts/synthesize_model.md`
```
You are converting a Java JPA @Entity to a Python SQLAlchemy 2.0 ORM model.

RULES:
1. Use `Mapped[T]` and `mapped_column()` syntax (SQLAlchemy 2.0+).
2. Map ALL JPA annotations:
   - @Id @GeneratedValue → primary_key=True, autoincrement
   - @Column(unique=true, nullable=false, length=N) → mapped_column(unique=True, nullable=False, String(N))
   - @OneToMany(mappedBy="x") → relationship(back_populates="x")
   - @ManyToOne → ForeignKey + relationship
   - @JoinColumn(name="x") → mapped_column(ForeignKey("table.x"))
   - @Enumerated(EnumType.STRING) → Enum column
   - @CreationTimestamp → server_default=func.now()
   - @UpdateTimestamp → onupdate=func.now()
3. Map ALL validation annotations to __table_args__ or CheckConstraint:
   - @NotNull → nullable=False
   - @Size(min=N, max=M) → CheckConstraint
   - @Email → leave as application-level validation
4. Preserve the exact table name from @Table(name="x").
5. Output ONLY Python code. No markdown, no explanation.

### JAVA SOURCE
{java_source}

### ENTITY CONTRACT (must satisfy all rules)
{contract_md}

### ALREADY GENERATED (for import references)
{existing_models}
```

#### `prompts/synthesize_service.md`
```
You are converting a Java @Service class to Python.

RULES:
1. Preserve 100% of the business logic — every if-branch, every validation, every side effect.
2. Convert @Autowired dependencies to __init__ constructor injection.
3. Convert @Transactional methods to use `async with session.begin():` blocks.
4. Convert Optional<T>.orElseThrow() to: `if not result: raise HTTPException(status_code=404)`.
5. Convert Java Stream API to Python list comprehensions.
6. Convert Java Exception types to FastAPI HTTPException with appropriate status codes.
7. For 3rd-party integrations, use the Python equivalent per the docs context.
8. Output ONLY Python code. No markdown, no explanation.

### JAVA SOURCE
{java_source}

### BUSINESS LOGIC CONTRACT (you MUST satisfy every rule listed here)
{contract_md}

### PYTHON DOCS CONTEXT (use these APIs — do NOT hallucinate different ones)
{docs_context}

### ALREADY GENERATED MODELS (use these exact class names and imports)
{existing_models}

### ALREADY GENERATED SCHEMAS (use these for request/response types)
{existing_schemas}
```

#### `prompts/synthesize_controller.md`
```
You are converting a Java @RestController to a FastAPI APIRouter.

RULES:
1. Map EVERY endpoint — don't skip any @GetMapping/@PostMapping/@PutMapping/@DeleteMapping.
2. Mapping rules:
   - @RestController → router = APIRouter(prefix="...", tags=["..."])
   - @GetMapping("/path") → @router.get("/path")
   - @PostMapping("/path") → @router.post("/path", status_code=201)
   - @PathVariable Long id → id: int = Path(...)
   - @RequestBody CreateDTO → body: CreateSchema
   - @RequestParam String q → q: str | None = Query(default=None)
   - @RequestHeader("Auth") → auth: str | None = Header(default=None)
   - @Valid → Pydantic handles validation automatically
   - @Autowired Service → service: Service = Depends(get_service)
   - ResponseEntity<T> → direct return (FastAPI serializes automatically)
   - ResponseEntity.status(201) → response_model + status_code param
3. Convert @ExceptionHandler to @router.exception_handler or app-level handler.
4. Preserve ALL input validation and error handling.
5. Output ONLY Python code. No markdown, no explanation.

### JAVA SOURCE
{java_source}

### API CONTRACT
{contract_md}

### ALREADY GENERATED SERVICES (use these for dependency injection)
{existing_services}

### ALREADY GENERATED SCHEMAS
{existing_schemas}
```

#### `prompts/synthesize_schema.md`
```
You are converting Java DTOs/Request/Response classes to Pydantic v2 BaseModel schemas.

RULES:
1. Map ALL fields with correct Python types.
2. Map validation annotations:
   - @NotNull / @NotBlank → Field(...) (required, no default)
   - @Size(min=N, max=M) → Field(min_length=N, max_length=M)
   - @Email → EmailStr (from pydantic)
   - @Min(N) → Field(ge=N)
   - @Max(N) → Field(le=N)
   - @Pattern(regexp="...") → Field(pattern="...")
3. Use `model_config = ConfigDict(from_attributes=True)` for ORM mapping.
4. Create both Request and Response variants if the Java code has separate DTOs.
5. Output ONLY Python code. No markdown, no explanation.

### JAVA SOURCE
{java_source}

### RELATED ENTITY CONTRACT
{contract_md}

### ALREADY GENERATED MODELS (for ORM compatibility)
{existing_models}
```

---

### 3.2 — Rewrite `LLMSynthesisService` with Context Injection

**File:** `app/services/llm_synthesis_service.py`

**New architecture:** The service accepts the full synthesis context and selects the right prompt template:

```python
class LLMSynthesisService:
    PROMPT_DIR = Path(__file__).parent.parent / "agents" / "prompts"

    async def synthesize_module(
        self,
        *,
        module_type: str,              # "models" | "schemas" | "services" | "controllers"
        java_source: str,              # raw Java source code
        contract_md: str,              # per-class .md contract
        docs_context: str,             # Python library docs
        existing_code: dict[str, str], # {"models": "...", "schemas": "...", ...} — already generated
        business_rules: list[str],
        discovered_tech: list[str],
    ) -> str:
        prompt_template = self._load_prompt(module_type)
        # Inject all context variables into the template
        ...
```

**Key innovation:** The `existing_code` dict passes previously-generated modules so the LLM uses correct import paths.

---

### 3.3 — Add Structured Output Parsing

Instead of hoping the LLM returns clean Python, enforce it:

```python
# After getting LLM response
content = self._strip_markdown_fences(response.content)

# Validate it's parseable Python
try:
    ast.parse(content)
except SyntaxError as e:
    # Retry with error context (up to 2 retries)
    content = await self._retry_with_error(content, str(e), prompt_context)

return content
```

---

### 3.4 — Add LLM Self-Correction Loop

If the generated code has syntax errors, ask the LLM to fix it:

```python
async def _retry_with_error(self, broken_code: str, error: str, original_context: dict) -> str:
    fix_prompt = (
        "The following Python code has a syntax error. Fix it.\n\n"
        f"ERROR: {error}\n\n"
        f"CODE:\n{broken_code}\n\n"
        "Return ONLY the fixed Python code."
    )
    response = await self.llm.ainvoke([HumanMessage(content=fix_prompt)])
    return self._strip_markdown_fences(response.content)
```

---

### 3.5 — Generate `app/main.py` and `app/core/config.py` Dynamically

Instead of hardcoded string templates, synthesize these from the actual IR:

- `main.py` should import all generated routers dynamically
- `config.py` should include settings for all detected technologies (DB URL, Redis URL, Kafka brokers, etc.)
- `db/session.py` should support the actual detected DB engine (PostgreSQL async, MySQL, SQLite)

---

### 3.6 — Generate `requirements.txt` from Full Tech Map

**File:** `app/services/output_generation_service.py` → `_render_requirements`

Complete mapping:

```python
TECH_TO_REQUIREMENTS = {
    # Core (always)
    "_core": ["fastapi", "uvicorn[standard]", "pydantic>=2.0", "pydantic-settings", "python-dotenv"],
    # Database
    "spring-data-jpa": ["sqlalchemy>=2.0", "alembic"],
    "hibernate": ["sqlalchemy>=2.0", "alembic"],
    "postgresql": ["asyncpg", "psycopg2-binary"],
    "mysql": ["pymysql", "aiomysql"],
    "mongodb": ["motor", "pymongo"],
    "redis": ["redis>=5.0"],
    # Messaging
    "kafka": ["aiokafka"],
    "rabbitmq": ["aio-pika"],
    # Auth
    "spring-security": ["python-jose[cryptography]", "passlib[bcrypt]"],
    "jwt": ["python-jose[cryptography]"],
    "bcrypt": ["passlib[bcrypt]"],
    # HTTP clients
    "feign": ["httpx"],
    "webclient": ["httpx"],
    "resttemplate": ["httpx"],
    # Third-party services
    "supabase": ["supabase"],
    "aws": ["boto3"],
    "gcp": ["google-cloud-storage"],
    "azure": ["azure-storage-blob"],
    # Utilities
    "lombok": [],  # No Python equivalent needed
    "mapstruct": [],  # Pydantic handles this
    "openapi-swagger": [],  # Built into FastAPI
    # Testing
    "_test": ["pytest", "pytest-asyncio", "httpx"],
}
```

---

### 3.7 — Add a `_get_chat_model_for_code` Variant

For code-heavy synthesis, use a larger context model if available:

```python
def get_code_model() -> BaseChatModel | None:
    """Returns a model optimized for long code generation."""
    # Prefer models with 128k+ context
    # Use lower temperature (0.05) for maximum determinism
    # Set max_tokens to 32768 for large service classes
    ...
```

---

## Phase 4 — Real Validation

> Transform from pseudo-check to a multi-layer validation gate.

### 4.1 — Python Syntax Validation

**File:** `app/services/validation_service.py`

```python
import ast

def _check_syntax(self, file_path: Path) -> list[str]:
    """Verify each generated file is valid Python."""
    try:
        source = file_path.read_text(encoding="utf-8")
        ast.parse(source)
        return []
    except SyntaxError as e:
        return [f"SyntaxError in {file_path.name}:{e.lineno} — {e.msg}"]
```

---

### 4.2 — Ruff Lint Integration

```python
import subprocess

def _check_lint(self, output_dir: Path) -> list[str]:
    """Run ruff linter on generated code."""
    result = subprocess.run(
        ["ruff", "check", str(output_dir), "--output-format=json", "--select=E,F,I"],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode == 0:
        return []
    
    import json
    findings = json.loads(result.stdout) if result.stdout else []
    return [
        f"ruff:{item['code']} in {item['filename']}:{item['location']['row']} — {item['message']}"
        for item in findings
    ]
```

---

### 4.3 — Import Resolution Check

```python
def _check_imports(self, output_dir: Path) -> list[str]:
    """Verify all imports resolve to generated files, stdlib, or requirements.txt."""
    generated_modules = self._build_module_index(output_dir)
    requirements = self._parse_requirements(output_dir / "requirements.txt")
    errors = []

    for py_file in output_dir.rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if not self._can_resolve(alias.name, generated_modules, requirements):
                        errors.append(f"Unresolved import '{alias.name}' in {py_file.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                if not self._can_resolve(node.module, generated_modules, requirements):
                    errors.append(f"Unresolved import '{node.module}' in {py_file.name}")
    return errors
```

---

### 4.4 — Structural Integrity Check

```python
def _check_structural_integrity(self, output_dir: Path, component_inventory: dict) -> list[str]:
    """Ensure every IR component has a generated file."""
    errors = []
    for entity in component_inventory.get("entities", []):
        expected = output_dir / "app" / "models" / f"{snake(entity['class_name'])}.py"
        if not expected.exists():
            errors.append(f"Missing model file for entity: {entity['class_name']}")
    
    for controller in component_inventory.get("controllers", []):
        expected = output_dir / "app" / "api" / "v1" / "endpoints" / f"{snake(controller['class_name'])}.py"
        if not expected.exists():
            errors.append(f"Missing router file for controller: {controller['class_name']}")
    # ... same for services, repositories
    return errors
```

---

### 4.5 — LLM Contract Compliance Check

```python
async def _check_contract_compliance(self, output_dir: Path, contracts_dir: Path) -> list[str]:
    """Ask the LLM to verify generated code satisfies each business contract."""
    violations = []
    for contract_file in contracts_dir.rglob("*.md"):
        contract = contract_file.read_text(encoding="utf-8")
        # Find the corresponding generated Python file
        generated_code = self._find_matching_code(output_dir, contract_file)
        if not generated_code:
            violations.append(f"No generated code found for contract: {contract_file.name}")
            continue

        prompt = (
            "Given this business logic contract:\n"
            f"<contract>\n{contract}\n</contract>\n\n"
            "And this generated Python code:\n"
            f"<code>\n{generated_code}\n</code>\n\n"
            "Does the Python code satisfy ALL rules in the contract?\n"
            "Return JSON: {\"compliant\": true/false, \"violations\": [\"...\"]}"
        )
        result = await self.llm.ainvoke([HumanMessage(content=prompt)])
        parsed = json.loads(result.content)
        if not parsed.get("compliant"):
            violations.extend(parsed.get("violations", []))
    return violations
```

---

### 4.6 — Fix the Retry Loop

**File:** `app/agents/graph.py`

```python
def should_retry_or_proceed(state: MigrationState) -> str:
    """Decide: retry current chunk, move to next chunk, or assemble."""
    errors = state.get("validation_errors", [])
    retry_count = state.get("retry_count", 0)

    if errors and retry_count < 3:
        # Retry the current chunk with error context injected
        return "migrate"

    # Pop current chunk (even if it failed after 3 retries — log and move on)
    remaining = state.get("metadata", {}).get("remaining_chunks", [])
    if remaining:
        return "migrate"

    return "assemble"
```

**Also update `validate_node`** to increment `retry_count` and inject error context into state so the next `migrate` call can include the errors in the LLM prompt.

---

## Phase 5 — Full-Fidelity Output Generation

> Handle every Spring Boot pattern, not just CRUD.

### 5.1 — Spring Security → FastAPI Security

**What to generate:**

```python
# app/core/security.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError

security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, settings.SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return user_id
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# Role-based access
def require_role(*roles: str):
    async def dependency(current_user = Depends(get_current_user)):
        # Fetch user role and check
        ...
    return dependency
```

**Detection:** The tech discovery already detects `spring-security`. Use the component discovery's `security` category to extract filter chain config, role definitions, and endpoint protection rules.

---

### 5.2 — `@Scheduled` Tasks → Background Tasks / APScheduler

Detect `@Scheduled` annotated methods and generate:

```python
# app/tasks/scheduled.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

@scheduler.scheduled_job('interval', seconds=300)
async def cleanup_expired_sessions():
    """Migrated from SessionCleanupService.cleanExpiredSessions()."""
    ...
```

Add `apscheduler` to the generated `requirements.txt`.

---

### 5.3 — Event-Driven (Kafka/RabbitMQ) → Python Equivalents

Detect `@KafkaListener`, `KafkaTemplate.send()`, `@RabbitListener`, `RabbitTemplate.convertAndSend()`.

Generate:

```python
# app/integrations/kafka_producer.py
from aiokafka import AIOKafkaProducer

producer = AIOKafkaProducer(bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS)

async def publish_event(topic: str, payload: dict):
    await producer.send_and_wait(topic, json.dumps(payload).encode())
```

---

### 5.4 — Cache Annotations → Python Caching

Detect `@Cacheable`, `@CacheEvict`, `@CachePut`.

Generate:

```python
from functools import lru_cache
# Or for Redis-backed:
from redis import asyncio as aioredis

cache = aioredis.from_url(settings.REDIS_URL)

async def get_cached(key: str):
    return await cache.get(key)
```

---

### 5.5 — Alembic Migration Generation

After generating SQLAlchemy models, generate an initial Alembic migration:

```
output/{job_id}/
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 001_initial.py
├── alembic.ini
```

The migration should `create_all` for every generated model.

---

### 5.6 — Docker and Docker Compose Generation

Generate proper multi-service Docker Compose based on detected technologies:

```yaml
# docker-compose.yml (generated)
services:
  app:
    build: .
    ports: ["8000:8000"]
    depends_on: [db]
    env_file: .env
  
  db:
    image: postgres:16   # or mysql:8.0
    environment:
      POSTGRES_DB: ${DB_NAME}
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes: ["db_data:/var/lib/postgresql/data"]
  
  redis:                  # only if redis detected
    image: redis:7
    ports: ["6379:6379"]
```

---

### 5.7 — Test Migration (JUnit → pytest)

For each `@Test` method in Java test classes, generate a pytest equivalent:

```python
# tests/test_user_service.py
import pytest
from app.services.user_service import UserService

class TestUserService:
    def test_create_user_with_valid_data(self):
        """Migrated from UserServiceTest.testCreateUserWithValidData."""
        service = UserService(repository=MockUserRepository())
        result = service.create_user(email="test@test.com", password="SecurePass1")
        assert result is not None
        assert result.email == "test@test.com"
```

---

### 5.8 — Multi-Module Project Support

Detect Maven/Gradle multi-module layouts (multiple `pom.xml` or `build.gradle`):

```
project/
├── common/src/main/java/...
├── api/src/main/java/...
├── service/src/main/java/...
└── pom.xml (parent)
```

Strategy: Flatten into a single FastAPI project but preserve the module boundary as Python packages:

```
output/
├── app/
│   ├── common/       ← from common module
│   ├── api/          ← from api module
│   └── service/      ← from service module
```

---

### 5.9 — Gradle Support

Currently Gradle files are detected but not parsed. Add:

```python
def _parse_gradle(self, build_gradle_text: str) -> list[str]:
    """Extract dependency coordinates from build.gradle."""
    # Match: implementation 'group:artifact:version'
    # Match: implementation "group:artifact:version"
    # Match: implementation("group:artifact:version")
    pattern = r"""(?:implementation|api|compile)\s*[\('"]+([^'")]+)"""
    return re.findall(pattern, build_gradle_text)
```

---

### 5.10 — Application Properties → Pydantic Settings

Parse `application.properties` / `application.yml` and generate a complete `Settings` class:

```python
# From: spring.datasource.url=jdbc:postgresql://localhost:5432/mydb
# Generate:
class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://user:pass@localhost:5432/mydb"
    redis_url: str = "redis://localhost:6379"  # from spring.redis.host
    kafka_bootstrap_servers: str = "localhost:9092"  # from spring.kafka.bootstrap-servers
    jwt_secret: str = "change-me"  # from jwt.secret
    jwt_expiration: int = 3600  # from jwt.expiration
```

---

## Phase 6 — Production Hardening

### 6.1 — SSE Real-Time Progress Streaming

**File:** `app/api/v1/migrate.py`

Add a Server-Sent Events endpoint:

```python
from fastapi.responses import StreamingResponse

@router.get("/{job_id}/stream")
async def stream_migration_progress(job_id: str):
    async def event_generator():
        last_step = ""
        while True:
            state = read_state_json(job_id)
            if state["current_step"] != last_step:
                last_step = state["current_step"]
                yield f"data: {json.dumps(state)}\n\n"
            if state["status"] in ("completed", "failed"):
                yield f"data: {json.dumps(state)}\n\n"
                break
            await asyncio.sleep(1)
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

---

### 6.2 — Workspace Cleanup

**File:** `app/services/cleanup_service.py`

```python
class CleanupService:
    MAX_AGE_HOURS = 24
    MAX_TOTAL_SIZE_GB = 10

    async def cleanup_stale_workspaces(self):
        """Remove workspaces older than MAX_AGE_HOURS."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.MAX_AGE_HOURS)
        for job_dir in settings.workspace_path.iterdir():
            if job_dir.stat().st_mtime < cutoff.timestamp():
                shutil.rmtree(job_dir)
```

Register as a periodic background task in the lifespan.

---

### 6.3 — Rate Limiting

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/github")
@limiter.limit("5/minute")
async def migrate_from_github(request: Request, ...):
    ...
```

---

### 6.4 — Configurable CORS

```python
# config.py
cors_origins: list[str] = ["http://localhost:5173"]  # default for Vite dev server

# main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    ...
)
```

---

### 6.5 — Proper Structured Logging with Loguru

**File:** `app/core/logging.py`

```python
from loguru import logger
import sys

def setup_logging():
    logger.remove()
    logger.add(sys.stderr, level=settings.log_level, format="{time} | {level} | {name} | {message}")
    logger.add("logs/spring2fast.log", rotation="10 MB", retention="7 days")
```

Replace all `logging.info()` calls with `logger.info()`.

---

### 6.6 — Alembic for Job Tracking DB

Replace `Base.metadata.create_all()` with proper Alembic migrations for the Spring2Fast app's own database.

---

### 6.7 — Pin Dependency Versions

**File:** `requirements.txt`

```
fastapi>=0.115.0,<1.0
uvicorn[standard]>=0.30.0
langchain-core>=0.3.0
langgraph>=0.2.0
sqlalchemy>=2.0.0,<3.0
# ... etc
```

---

### 6.8 — Integration Test Suite

**New directory:** `tests/integration/`

Test the full pipeline with a sample Spring Boot project:

```python
@pytest.mark.asyncio
async def test_full_migration_petclinic():
    """Test full pipeline with Spring PetClinic."""
    orchestrator = MigrationOrchestrator()
    result = await orchestrator.run_migration(
        job_id="test-001",
        source_type="github",
        source_url="https://github.com/spring-projects/spring-petclinic",
    )
    assert result["status"] == "completed"
    assert len(result["generated_files"]) > 10
    assert len(result["validation_errors"]) == 0
```

---

## Execution Order

```
Phase 0 (1 day)   → Fix the 4 runtime bugs
Phase 1 (3 days)  → Java AST parsing + IR dataclasses
Phase 2 (2 days)  → Per-service .md contracts
Phase 3 (5 days)  → LLM synthesis overhaul (highest ROI)
Phase 4 (3 days)  → Real validation pipeline
Phase 5 (5 days)  → Full-fidelity generation (security, events, etc.)
Phase 6 (3 days)  → Production hardening
                    ────────────
                    ~22 days total
```

## Definition of "100% Ready"

A migration is 100% when the output project:

1. **Compiles** — `python -c "import app"` succeeds
2. **Lints clean** — `ruff check` returns 0 errors
3. **Is formatted** — `black --check` passes
4. **All imports resolve** — no unresolved imports
5. **Preserves all endpoints** — every Java `@*Mapping` has a FastAPI `@router.*`
6. **Preserves all entities** — every `@Entity` has a SQLAlchemy model
7. **Preserves all business logic** — LLM contract compliance check passes
8. **Runs** — `uvicorn app.main:app` starts without errors
9. **Has dependencies** — `requirements.txt` includes everything needed
10. **Has config** — `.env.example` covers all settings
11. **Has Docker** — `docker-compose up` builds and runs
12. **Has tests** — `pytest` discovers and runs generated test stubs
13. **Has docs** — `README.md` + `docs/contracts/` for audit trail
