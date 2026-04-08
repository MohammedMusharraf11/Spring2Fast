# Spring2Fast — Phase 2 Implementation Plan

> **Strategic Recommendation up front:**
> Do NOT prioritize non-REST (Thymeleaf/MVC) support.
> Teams migrating Spring Boot → FastAPI specifically want to go **API-first**.
> Supporting MVC is a dead end — nobody wants a Python Thymeleaf clone.
> Fix quality first, then expand to microservices. Details below.

---

## Why NOT Thymeleaf/MVC Support?

When a team migrates from Spring Boot to FastAPI, they are making a **deliberate architectural decision** to go API-first. They are not looking for a Python clone of Thymeleaf — they are decoupling their frontend entirely. Supporting MVC would mean:

1. Building a Jinja2/HTMX migration path that nobody asked for
2. Adding enormous complexity for a use case that is architecturally backward
3. Competing with tools like `htmx` adoption which is a totally separate market

**Instead:** When Spring2Fast encounters a `@Controller` (MVC, non-REST), it should **automatically redesign** it as a REST API — extract the data, drop the view layer. This is the right migration path.

---

## Current State Assessment

### What's Broken (Real failures observed)

| Issue | Severity | Root Cause |
|---|---|---|
| `services/` directory empty on large repos | 🔴 Critical | Groq 429 mid-pipeline, empty fallback |
| JPA `@MappedSuperclass` fields missing | 🔴 Critical | Converter only reads immediate class, not superchain |
| `FIXME: unresolved` import comments | 🔴 Critical | `_fix_imports()` comments out instead of resolving |
| `@Query` JPQL → `raise NotImplementedError` | 🟡 High | No JPQL translator |
| No `id` primary key on models | 🟡 High | Base class not read |
| Thymeleaf routes generate `pass` stubs | 🟡 High | MVC route → no REST equivalent |
| Models missing `name`/`firstName` etc | 🟡 High | `@MappedSuperclass` not traversed |
| No `app/db/session.py` generated | 🟡 High | `get_db` dependency always FIXME-commented |

### What's Working Well
- Component discovery (entities, services, controllers, repos) ✅
- 3-tier LLM routing (Bedrock → Groq → Gemini) ✅
- Project structure generation ✅
- Basic business logic translation ✅
- GitHub push ✅
- Real-time UI ✅

---

## Phase 1 — Quality Hardening (Week 1–2)

> Goal: Make every REST API migration **run-ready out of the box** with no manual fixes.

### 1.1 Fix JPA Inheritance & `@MappedSuperclass` Field Resolution 🔴

**Problem:** `Owner extends Person` → generated `Owner` model is missing `firstName`, `lastName`, `id`.

**Solution:** Before converting any entity, the component discovery service should resolve the **full ancestor chain** and merge all fields.

**Files to change:**
- `app/services/component_discovery_service.py` — add `_resolve_superclass_fields()`
- `app/agents/converter_agents/model_converter.py` — accept `inherited_fields` in prompt context

```python
# New flow:
# 1. Parse @MappedSuperclass files first → build field registry
# 2. For each @Entity, merge own fields + all ancestor fields
# 3. Pass merged field list to model converter LLM prompt

INHERITED_FIELDS_PROMPT = """
The following fields are INHERITED from superclasses and MUST be included:
{inherited_fields}

Do NOT skip them. Include them before the entity's own fields.
"""
```

**Expected outcome:** `Owner` model gets `id`, `first_name`, `last_name` from `Person`.

---

### 1.2 Fix `get_db` and Session Infrastructure Generation 🔴

**Problem:** Every endpoint has `# FIXME: unresolved — from app.db.session import get_db`. The file `app/db/session.py` is never generated.

**Solution:** The `assemble_node` should generate a set of **infrastructure stubs** that are always needed regardless of the source repo:

**New file: `app/db/session.py`** (always generated)
```python
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from app.config import settings

engine = create_async_engine(settings.database_url)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
```

**New file: `app/core/security.py`** (generated if JWT detected)
```python
# JWT dependency injection stub — Spring Security → FastAPI
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
...
```

**Files to change:**
- `app/agents/nodes/assemble.py` — add `_generate_infrastructure_files()` call
- New: `app/agents/infra_templates/` directory with Jinja2 templates for `session.py`, `security.py`, `config.py`, `main.py`

---

### 1.3 Fix `FIXME: unresolved` Import Resolution 🔴

**Problem:** `_fix_imports()` in `base.py` currently **comments out** unresolved imports. They should be **resolved or scaffolded** instead.

**Better strategy:**
1. Build an **output file registry** as files are written (map class name → output path)
2. When an import is unresolved, look it up in the registry and rewrite the path
3. Only comment out if genuinely unresolvable

```python
# In BaseConverterAgent — replace _fix_imports():
def _resolve_imports(self, code: str, output_registry: dict[str, str]) -> str:
    """Rewrite imports using the known output file registry.
    
    output_registry = {"OwnerService": "app/services/owner.py", ...}
    """
    # For each from X import Y where Y is a known class:
    # → rewrite X to the correct module path
    # Only comment out if Y is not in registry at all
```

**Files to change:**
- `app/agents/converter_agents/base.py` — replace `_fix_imports()` with `_resolve_imports()`
- `app/agents/migration_subgraph/converter_nodes.py` — pass `output_registry` to each agent
- `app/agents/state.py` — add `output_registry: dict[str, str]` to `MigrationState`

---

### 1.4 JPQL → SQLAlchemy Query Translator 🟡

**Problem:** `@Query("SELECT u FROM User u WHERE ...")` → `raise NotImplementedError`.

**Solution:** New `JPQLTranslator` class using the LLM with a specialized prompt. This is the highest-value prompt engineering task — it directly fills the biggest hole in the repo converter.

```python
# New: app/agents/tools/jpql_translator.py
class JPQLTranslator:
    """Translates JPQL / Spring Data method names to SQLAlchemy select() statements."""
    
    async def translate(self, jpql: str, entity: str, session_var: str = "self.db") -> str:
        """
        Input:  "SELECT u FROM User u WHERE u.email = :email"
        Output: "result = await self.db.execute(select(User).where(User.email == email))\n
                 return result.scalar_one_or_none()"
        """
```

**Also translate Spring Data method names:**
```
findByEmail(String email)         → select(User).where(User.email == email)
findByLastNameOrderByFirst()      → select(Owner).where(...).order_by(Owner.first_name)
existsByEmail(String email)       → select(exists().where(User.email == email))
countByStatus(String status)      → select(func.count()).where(...)
deleteByCreatedAtBefore(Date d)   → delete(Entity).where(...)
```

**Files to change:**
- New: `app/agents/tools/jpql_translator.py`
- `app/agents/converter_agents/repo_converter.py` — call JPQL translator before LLM
- `app/agents/converter_agents/base.py` — add deterministic conversion tier for repos

---

### 1.5 MVC Controller → REST API Redesign (instead of stubs) 🟡

**Problem:** `@Controller` (Thymeleaf) methods generate `pass` bodies.

**Better approach:** Auto-redesign MVC controllers as REST endpoints. Extract the **data** the controller was preparing and return it as JSON.

```
Java MVC (before):               FastAPI REST (after):
@GetMapping("/owners/{id}")       @router.get("/owners/{id}")
ModelAndView showOwner(id) {      async def get_owner(id: int, db=Depends(get_db)):
  Owner owner = service.find(id)    owner = await service.get_by_id(id)
  model.addAttribute("owner",owner) return OwnerResponse.model_validate(owner)
  return new MAV("owner/details")
}
```

The converter prompt should explicitly instruct: "If the Java method returns a View (ModelAndView, String view name), convert it to return the data as JSON instead."

**Files to change:**
- `app/agents/converter_agents/controller_converter.py` — update prompt template
- `app/agents/prompts/synthesize_controller.md` — stronger instruction on MVC → REST redesign

---

## Phase 2 — Infrastructure Generation (Week 2–3)

> Goal: The generated project should be **immediately runnable** — `pip install -r requirements.txt && uvicorn app.main:app` should just work.

### 2.1 Alembic Migration Generation 🟡

**What it does:** Reads the generated SQLAlchemy models and auto-generates an Alembic `env.py` + initial migration.

```
output/
├── alembic/
│   ├── env.py              ← auto-generated, imports app/models/__init__.py
│   ├── script.py.mako
│   └── versions/
│       └── 0001_initial.py ← generated from discovered entities
└── alembic.ini
```

**Implementation:**
- Post-assemble step: parse all generated models → extract table definitions → write Alembic revision
- Use `alembic` programmatic API to generate the file

**Files to add:**
- `app/agents/generators/alembic_generator.py`
- Called from `assemble_node` after ZIP packaging

---

### 2.2 Docker + Docker Compose Generation 🟡

**What it does:** Generates a working `Dockerfile` and `docker-compose.yml` for the output project.

```dockerfile
# Generated Dockerfile (tailored to detected Python version + dependencies)
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
# Generated docker-compose.yml
services:
  api:
    build: .
    ports: ["8000:8000"]
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/app
    depends_on: [db]
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_PASSWORD: postgres
```

**Tailoring based on discovered tech:**
- MySQL detected → use `mysql+asyncmy` driver
- Redis detected → add Redis service
- Kafka detected → add Zookeeper + Kafka services

**Files to add:**
- `app/agents/generators/docker_generator.py`
- Called from `assemble_node`

---

### 2.3 pytest Skeleton Generation 🟡

**What it does:** For every generated service and endpoint, generate a basic pytest test file with correct structure.

```python
# Generated: tests/test_owner_service.py
import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_get_owner_by_id():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/v1/owners/1")
    assert response.status_code in (200, 404)  # TODO: seed DB

@pytest.mark.asyncio
async def test_create_owner():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/api/v1/owners", json={
            "first_name": "John",  # TODO: fill from schema
        })
    assert response.status_code == 201
```

**Files to add:**
- `app/agents/generators/test_generator.py`
- `app/agents/converter_agents/test_converter.py` (new agent type)

---

### 2.4 Pydantic Schema Improvements 🟡

**Current problem:** Generated schemas often use generic `Optional` without proper field constraints from Java `@NotNull`, `@Size`, `@Email` annotations.

**Solution:** Parse Java Bean Validation annotations → map to Pydantic field validators.

```
Java:                                    Pydantic:
@NotNull                          →      field: str  (non-optional)
@Size(min=1, max=255)             →      field: str = Field(..., min_length=1, max_length=255)
@Email                            →      field: EmailStr
@Pattern(regexp="...")            →      field: str = Field(..., pattern="...")
@Min(0) @Max(100)                 →      field: int = Field(..., ge=0, le=100)
@NotBlank                         →      field: str = Field(..., min_length=1)
```

**Files to change:**
- `app/agents/tools/converter_tools.py` — add `parse_bean_validation()` function
- `app/agents/converter_agents/schema_converter.py` — feed validators into prompt

---

## Phase 3 — Scope Expansion (Week 3–5)

> Goal: Handle real-world enterprise patterns beyond simple CRUD.

### 3.1 Feign Client → httpx Service Client 🟡

**What it does:** Detects `@FeignClient` interfaces in microservice repos and converts them to async `httpx` client classes.

```java
// Java
@FeignClient(name="user-service", url="${user.service.url}")
interface UserClient {
    @GetMapping("/users/{id}")
    UserDto getUser(@PathVariable Long id);
}
```

```python
# Generated Python
import httpx
from app.config import settings

class UserServiceClient:
    def __init__(self):
        self.base_url = settings.user_service_url
    
    async def get_user(self, user_id: int) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.base_url}/users/{user_id}")
            resp.raise_for_status()
            return resp.json()
```

**Files to add:**
- `app/agents/converter_agents/feign_converter.py`
- Update `component_discovery_service.py` to detect `@FeignClient`

---

### 3.2 Kafka / RabbitMQ Event Handlers 🟡

**Detects:** `@KafkaListener`, `@RabbitListener`, `@EventListener`

**Generates:** FastStream or aiokafka consumer stubs

```python
# Generated: app/consumers/order_consumer.py
from aiokafka import AIOKafkaConsumer
import asyncio, json

async def consume_orders():
    consumer = AIOKafkaConsumer(
        "orders",
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id="order-group"
    )
    await consumer.start()
    try:
        async for msg in consumer:
            data = json.loads(msg.value)
            await handle_order_event(data)
    finally:
        await consumer.stop()
```

---

### 3.3 Spring Cache → Redis Cache Layer 🟡

**Detects:** `@Cacheable`, `@CacheEvict`, `@CachePut`

**Generates:** `aiocache` / `redis-py` decorators on the appropriate service methods.

```python
# Generated
from aiocache import cached, Cache

@cached(ttl=300, cache=Cache.REDIS, key_builder=lambda f, self, id: f"owner:{id}")
async def get_by_id(self, owner_id: int) -> Owner | None:
    ...
```

---

### 3.4 `@Scheduled` → APScheduler / Celery Beat 🟡

**Detects:** `@Scheduled(fixedRate=...)`, `@Scheduled(cron="...")`

**Generates:** APScheduler-based background task setup.

```python
# Generated: app/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

@scheduler.scheduled_job("interval", seconds=60)
async def cleanup_expired_sessions():
    # Migrated from @Scheduled(fixedRate=60000)
    ...
```

---

## UI Improvements (Parallel Track)

### UI-1: Validation Report Panel
Show the `validation_report` from `_state.json` in the UI — display each issue with file, line, type (FIXME/CONTRACT/IMPORT), and severity. Currently hidden in logs.

### UI-2: File Diff View
Side-by-side view: original Java source on the left, generated Python on the right. Per-component. This is the killer feature for demo purposes.

### UI-3: Re-run Single Component
Allow re-generating a single file after migration without re-running the whole pipeline. User clicks a file in the output browser → "Regenerate" button → sends component back through the converter agent.

### UI-4: Migration Comparison Score
After migration, run a quick structural comparison and show a **Migration Fidelity Score:**
```
Models:      ████████████ 95%  (19/20 fields matched)
Controllers: ██████████░░ 85%  (17/20 routes matched)
Services:    ████████░░░░ 72%  (13/18 methods complete)
Overall:     █████████░░░ 84%
```

---

## Implementation Priority Order

```
Week 1:  1.2 (Infrastructure stubs) → 1.1 (JPA inheritance) → 1.3 (Import resolution)
Week 2:  1.4 (JPQL translator) → 1.5 (MVC → REST redesign) → 2.4 (Pydantic validators)
Week 3:  2.1 (Alembic) → 2.2 (Docker) → 2.3 (pytest skeletons)
Week 4:  3.1 (Feign → httpx) → UI-1 (Validation panel) → UI-2 (Diff view)
Week 5:  3.2 (Kafka) → 3.3 (Cache) → UI-3 (Re-run single) → UI-4 (Score)
```

---

## Effort Estimates

| Item | Effort | Impact | Priority |
|---|---|---|---|
| 1.2 Infrastructure stubs | 2h | 🔴 Fixes every generated project | **Start here** |
| 1.1 JPA inheritance | 4h | 🔴 Fixes model correctness | **P0** |
| 1.3 Import resolution | 6h | 🔴 Eliminates all FIXME comments | **P0** |
| 1.4 JPQL translator | 8h | 🟡 Fills biggest repo gap | **P1** |
| 1.5 MVC → REST redesign | 3h | 🟡 Turns stubs into real routes | **P1** |
| 2.4 Pydantic validators | 4h | 🟡 Better schema quality | **P1** |
| 2.1 Alembic | 6h | 🟡 Run-ready DB setup | **P2** |
| 2.2 Docker | 3h | 🟡 One-command deployment | **P2** |
| 2.3 pytest skeletons | 4h | 🟡 QA scaffolding | **P2** |
| UI-2 Diff view | 8h | ✨ Killer demo feature | **P2** |
| 3.1 Feign → httpx | 6h | 🟡 Microservice support | **P3** |
| UI-3 Re-run component | 5h | ✨ Great UX | **P3** |
| UI-4 Fidelity score | 6h | ✨ Standout feature | **P3** |
| 3.2–3.4 Kafka/Cache/Scheduler | 12h | 🟢 Enterprise expansion | **P4** |

---

## What NOT to Build (Tradeoffs)

| Rejected Feature | Why |
|---|---|
| Thymeleaf → Jinja2 migration | Wrong direction — teams want API-first, not view cloning |
| Spring Batch full support | Too niche; Celery stub is sufficient |
| Spring Cloud full microservice mesh | Too much scope; Feign → httpx covers 80% of the value |
| GraphQL Spring → Strawberry | Niche enough to be a separate project |
| Java → FastAPI code review (LLM critic) | Diminishing returns; fidelity score covers this |

> [!IMPORTANT]
> The single highest-ROI item is **1.2 (Infrastructure stubs)** — fixing `get_db`, `session.py`, and `main.py` generation makes every single migration run-ready immediately. This one change removes the most common source of manual effort post-migration.
