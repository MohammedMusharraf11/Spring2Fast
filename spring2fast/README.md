# Spring2Fast 🚀

**Agentic AI system that migrates Java Spring Boot backends to Python FastAPI — automatically.**

Spring2Fast uses a LangGraph-powered DAG pipeline with specialized converter agents to analyze, plan, and convert your Spring Boot codebase into a fully functional FastAPI project.

---

## Architecture

```
                              ┌──────────────┐
                              │    ingest     │  ← Clone repo / extract ZIP
                              └──────┬───────┘
                         ╱           │           ╲
              ┌──────────────┐ ┌───────────┐ ┌───────────────────┐
              │ tech_discover│ │ biz_logic │ │discover_components│  ← Parallel DAG
              └──────┬───────┘ └─────┬─────┘ └────────┬──────────┘
                         ╲           │           ╱
                              ┌──────┴───────┐
                              │merge_analysis│  ← Fan-in
                              └──────┬───────┘
                              ┌──────┴───────┐
                              │research_docs │  ← Fetch Python lib docs
                              └──────┬───────┘
                              ┌──────┴───────┐
                              │   analyze    │  ← Dependency graph
                              └──────┬───────┘
                              ┌──────┴───────┐
                              │     plan     │  ← Build conversion queue
                              └──────┬───────┘
                         ┌───────────┴───────────────┐
                         │   MIGRATION SUBGRAPH      │
                         │                           │
                         │  supervisor → converter   │  ← Processes each component
                         │      ↑            ↓       │     model → schema → repo →
                         │      └── quality_gate     │     service → controller → config
                         └───────────┬───────────────┘
                              ┌──────┴───────┐
                              │   validate   │──→ retry if errors
                              └──────┬───────┘
                              ┌──────┴───────┐
                              │   assemble   │  ← ZIP output
                              └──────────────┘
```

### Conversion Tiers

| Tier | Method | When Used |
|------|--------|-----------|
| **Tier 1** | Deterministic (no LLM) | Simple entities, basic repositories — fast, reliable |
| **Tier 2** | LLM synthesis | Services, controllers, complex logic — uses fine-tuned prompts |
| **Tier 3** | Fallback scaffold | LLM unavailable — generates TODO-commented skeleton |

### Converter Agents

| Agent | Converts | Output |
|-------|----------|--------|
| `model_converter` | `@Entity` | SQLAlchemy models with relationships |
| `schema_converter` | DTOs | Pydantic v2 `Create`/`Update`/`Response` schemas |
| `repo_converter` | `@Repository` | SQLAlchemy repository classes |
| `service_converter` | `@Service` | Business logic classes with dependency injection |
| `controller_converter` | `@RestController` | FastAPI routers with `Depends()` wiring |
| `exception_converter` | `@ControllerAdvice` | FastAPI exception handlers |
| `config_converter` | Configuration | `main.py`, `config.py`, `db/`, `deps.py`, `requirements.txt`, etc. |

---

## What Works Today ✅

### Fully Supported (100%)
- **Simple CRUD** — REST APIs with entities, repos, services, controllers
- **JPA Relationships** — `@ManyToOne`, `@OneToMany`, `@ManyToMany` → SQLAlchemy relationships
- **Bean Validation** — `@NotNull`, `@Size`, `@Email` → Pydantic field constraints
- **JWT / Spring Security** — auto-detects and wires `Depends(get_current_user)`
- **Custom Exception Handlers** — `@ControllerAdvice` → FastAPI exception handlers
- **Multi-entity Business Logic** — complex services with conditionals, loops, try/catch
- **Project Scaffolding** — generates 20+ infrastructure files (main.py, config, db, deps, router, requirements.txt, .env, README)

### Partially Supported (70-85%)
- **PostgreSQL/MySQL** — correct async driver, but no Alembic migrations
- **Redis caching** — detected, added to deps, but `@Cacheable` not auto-converted
- **File uploads** — `MultipartFile` → `UploadFile` via LLM

### Not Yet Implemented ⬜
- Kafka / RabbitMQ event-driven
- `@Scheduled` / Cron jobs
- WebSocket / GraphQL / gRPC
- `@FeignClient` / `RestTemplate` inter-service calls
- Multi-module Maven projects

---

## Quick Start

### Prerequisites
- Python 3.11+
- Google Gemini API key (for LLM-powered conversions)

### 1. Clone & Install

```bash
git clone <repo-url>
cd spring2fast
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
```

Edit `.env`:
```env
GEMINI_API_KEY=your_api_key_here
# Optional: for docs research
SERPER_API_KEY=your_serper_key
```

### 3. Run

```bash
python main.py
```

The server starts at `http://localhost:8000`.

- **Swagger docs:** http://localhost:8000/docs
- **API base:** http://localhost:8000/api/v1/

### 4. Start a Migration

**From GitHub:**
```bash
curl -X POST http://localhost:8000/api/v1/migrate/github \
  -H "Content-Type: application/json" \
  -d '{"github_url": "https://github.com/user/spring-boot-project", "branch": "main"}'
```

**From ZIP upload:**
```bash
curl -X POST http://localhost:8000/api/v1/migrate/upload \
  -F "file=@my-spring-project.zip"
```

### 5. Track Progress
```bash
curl http://localhost:8000/api/v1/migrate/{job_id}/state
```

### 6. Download Result
```bash
curl -o result.zip http://localhost:8000/api/v1/migrate/{job_id}/result
```

---

## Frontend (spring2fast-ui)

A React + Vite dashboard for visual migration tracking.

```bash
cd spring2fast-ui
npm install
npm run dev
```

Open `http://localhost:5173` — connect to the backend at `http://localhost:8000`.

### Features
- Real-time DAG pipeline visualization
- Source file browser (Java)
- Generated code browser (Python)
- Artifact viewer (contracts, analysis reports)
- Conversion stats dashboard
- Live logs viewer
- ZIP download on completion

---

## Project Structure

```
spring2fast/
├── main.py                          # Entry point: python main.py
├── requirements.txt
├── .env.example
│
├── app/
│   ├── main.py                      # FastAPI app factory
│   ├── config.py                    # Settings (env vars)
│   ├── database.py                  # SQLite async DB
│   │
│   ├── agents/                      # LangGraph pipeline
│   │   ├── state.py                 # Shared state (TypedDict with reducers)
│   │   ├── graph.py                 # DAG builder + compiled graph
│   │   │
│   │   ├── nodes/                   # Pipeline nodes
│   │   │   ├── ingest.py
│   │   │   ├── tech_discover.py
│   │   │   ├── extract_business_logic.py
│   │   │   ├── discover_components.py
│   │   │   ├── merge_analysis.py
│   │   │   ├── research_docs.py
│   │   │   ├── analyze.py
│   │   │   ├── plan_migration.py
│   │   │   ├── validate.py
│   │   │   └── assemble.py
│   │   │
│   │   ├── migration_subgraph/      # Supervisor subgraph
│   │   │   ├── graph.py             # Subgraph builder
│   │   │   ├── supervisor.py        # Routes components to converters
│   │   │   ├── converter_nodes.py   # Node wrappers + scaffold generator
│   │   │   └── quality_gate.py      # Conversion quality check
│   │   │
│   │   ├── converter_agents/        # Specialized converter agents
│   │   │   ├── base.py              # Inner loop: parse → convert → validate → write
│   │   │   ├── model_converter.py
│   │   │   ├── schema_converter.py
│   │   │   ├── repo_converter.py
│   │   │   ├── service_converter.py
│   │   │   ├── controller_converter.py
│   │   │   └── exception_converter.py
│   │   │
│   │   ├── prompts/                 # LLM prompt templates
│   │   │   ├── synthesize_model.md
│   │   │   ├── synthesize_schema.md
│   │   │   ├── synthesize_service.md
│   │   │   ├── synthesize_controller.md
│   │   │   └── synthesize_exception_handler.md
│   │   │
│   │   └── tools/                   # Shared tools (parse, convert, validate, write)
│   │       └── converter_tools.py
│   │
│   ├── services/                    # Business logic services
│   │   ├── migration_orchestrator.py
│   │   ├── ingestion_service.py
│   │   ├── java_ast_parser.py
│   │   ├── technology_inventory_service.py
│   │   ├── business_logic_service.py
│   │   ├── business_logic_contract_service.py
│   │   ├── component_discovery_service.py
│   │   ├── docs_research_service.py
│   │   ├── analysis_service.py
│   │   ├── migration_planning_service.py
│   │   ├── validation_service.py
│   │   └── llm_synthesis_service.py
│   │
│   ├── api/                         # REST endpoints
│   │   ├── router.py
│   │   └── v1/
│   │       └── migrate.py           # 12 migration endpoints
│   │
│   ├── models/                      # DB models + Pydantic schemas
│   ├── repositories/                # Data access layer
│   └── core/                        # LLM client, logging
│
├── tests/                           # Test suite
│   ├── conftest.py
│   └── unit/
│
└── workspace/                       # Runtime: cloned repos, artifacts, output (gitignored)
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/migrate/github` | Start migration from GitHub URL |
| `POST` | `/api/v1/migrate/upload` | Start migration from ZIP upload |
| `GET` | `/api/v1/migrate/{id}/status` | Job status (lightweight) |
| `GET` | `/api/v1/migrate/{id}/state` | Full state with logs, stats, conversions |
| `GET` | `/api/v1/migrate/{id}/result` | Download generated ZIP |
| `GET` | `/api/v1/migrate/{id}/artifacts` | List analysis artifacts |
| `GET` | `/api/v1/migrate/{id}/artifact/{file}` | View artifact content |
| `GET` | `/api/v1/migrate/{id}/source-tree` | Browse Java source tree |
| `GET` | `/api/v1/migrate/{id}/source-file` | View Java source file |
| `GET` | `/api/v1/migrate/{id}/output-tree` | Browse generated Python tree |
| `GET` | `/api/v1/migrate/{id}/output-file` | View generated Python file |
| `GET` | `/api/v1/migrate/jobs/list` | List all migration jobs |

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | FastAPI + Python 3.11+ |
| Pipeline | LangGraph (DAG with subgraphs) |
| LLM | Google Gemini (via LangChain) |
| Database | SQLite (async, aiosqlite) |
| Java Parsing | Regex + custom AST parser |
| Frontend | React + Vite |

---

## License

MIT
