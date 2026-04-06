<div align="center">

<img src="https://img.shields.io/badge/Spring_Boot-6DB33F?style=for-the-badge&logo=spring-boot&logoColor=white" alt="Spring Boot"/>
<img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI"/>
<img src="https://img.shields.io/badge/LangGraph-FF6B35?style=for-the-badge&logo=langchain&logoColor=white" alt="LangGraph"/>
<img src="https://img.shields.io/badge/AWS_Bedrock-FF9900?style=for-the-badge&logo=amazon-aws&logoColor=white" alt="AWS Bedrock"/>

# Spring2Fast

### Autonomous Java Spring Boot → Python FastAPI Migration Agent

*An agentic AI pipeline that fully migrates Java Spring Boot backends to production-ready Python FastAPI — models, services, repositories, controllers, schemas, and all.*

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-orange)](https://langchain-ai.github.io/langgraph/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

---

## What is Spring2Fast?

Spring2Fast is an **agentic AI migration system** that converts a Java Spring Boot repository — directly from a GitHub URL or a uploaded ZIP — into a fully structured Python FastAPI project. It doesn't just translate syntax; it understands the architecture of your Java backend and reconstructs it idiomatically in Python.

You point it at a GitHub repo. It returns a runnable FastAPI project.

---

## Architecture

Spring2Fast uses a **multi-agent DAG pipeline** built on LangGraph. Each phase is a specialised agent with a distinct responsibility. Agents run in parallel where safe and sequentially where order matters.

```
GitHub / ZIP URL
       │
       ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        INGESTION                                     │
│  Clone/extract source → normalise file tree → build input index      │
└─────────────────────┬───────────────────────────────────────────────┘
                      │
          ┌───────────┼───────────┐   (parallel)
          ▼           ▼           ▼
   ┌────────────┐ ┌──────────┐ ┌───────────────────┐
   │  Tech       │ │ Business │ │ Component          │
   │  Discovery  │ │ Logic    │ │ Discovery          │
   │             │ │ Extractor│ │                    │
   │ Scans deps, │ │ Extracts │ │ Classifies every   │
   │ build system│ │ domain   │ │ @Entity, @Service, │
   │ Spring vers │ │ rules &  │ │ @Repository,       │
   │ integrations│ │ contracts│ │ @RestController    │
   └──────┬──────┘ └────┬─────┘ └──────────┬─────────┘
          └─────────────┴──────────────────┘
                        │
                        ▼
              ┌──────────────────┐
              │  Merge Analysis  │
              │  Docs Research   │
              │  (MCP / Serper)  │
              └────────┬─────────┘
                       │
                       ▼
              ┌─────────────────┐
              │  Migration Plan  │
              │  (per-component  │
              │  ordered queue)  │
              └────────┬────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    CODE GENERATION   (LangGraph Subgraph)             │
│                                                                       │
│  For every component in the plan, a specialised Converter Agent runs: │
│                                                                       │
│   ┌──────────────────────────────────────────────┐                   │
│   │  1. Read Java source + extracted contract     │                   │
│   │  2. Try deterministic conversion (Tier 1)     │                   │
│   │  3. LLM synthesis with architecture prompt    │                   │
│   │     → AWS Bedrock Llama 4 Maverick            │                   │
│   │  4. Inner validation loop (syntax + imports)  │                   │
│   │  5. Self-correction if needed (max 2 retries) │                   │
│   │  6. Write output file                         │                   │
│   └──────────────────────────────────────────────┘                   │
│                                                                       │
│  Converter Agents: Model │ Repository │ Service │ Controller │ Schema │
└──────────────────────────────────────────────────────────────────────┘
                       │
                       ▼
              ┌─────────────────┐
              │   Validation    │
              │  (advisory)     │
              │  AST syntax +   │
              │  import checks  │
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │    Assembly     │
              │  Post-process   │
              │  Import fix     │
              │  ZIP / GitHub   │
              └─────────────────┘
```

---

## Key Features

### 🤖 Intelligent Component Discovery
Spring2Fast scans your entire Java codebase using `javalang` AST parsing to identify and classify:
- `@Entity` → SQLAlchemy `Mapped[]` models
- `@RestController` / `@Controller` → FastAPI `APIRouter` endpoints
- `@Service` / `@ServiceImpl` → Python service classes
- `@Repository` / `JpaRepository<T,ID>` → async SQLAlchemy repository pattern
- `@Component` / `@Configuration` → Python configuration modules

### ⚡ 3-Tier LLM Routing
Spring2Fast routes tasks to the optimal model with zero manual configuration:

| Task | Model | Reason |
|---|---|---|
| **Code generation** | AWS Bedrock — Llama 4 Maverick | No RPM limits, strongest at code |
| **Analysis & planning** | AWS Bedrock — Llama 4 Maverick | Safe for parallel agents, no rate limits |
| **Fallback** | Groq → Gemini Flash | Automatic cascade if Bedrock unavailable |

### 🔄 Inner Validation Loop
Every converter agent independently validates its own output before returning:
1. Python AST syntax check
2. Import resolution check
3. LLM-driven self-correction (up to 2 attempts)

This catches ~80% of issues without requiring expensive pipeline retries.

### 📡 Real-Time Progress Tracking
A React + Vite frontend provides live pipeline visibility:
- Animated DAG workflow showing each agent's status
- Real-time log streaming
- Source file browser (original Java)
- Generated code browser (output Python)
- Artifact viewer (contracts, tech inventory, business rules)

### 🚀 One-Click GitHub Push
When migration completes, push directly to a new GitHub repository — no download needed. The server uses `GITHUB_PAT` from `.env` automatically.

---

## Tech Stack

### Backend
| Layer | Technology |
|---|---|
| API Framework | FastAPI + Uvicorn |
| Agent Orchestration | LangGraph (stateful DAG) |
| LLM SDK | LangChain (AWS, Groq, Google, OpenAI) |
| Primary LLM | AWS Bedrock — Llama 4 Maverick |
| Java Parsing | `javalang`, `tree-sitter` |
| Persistence | Supabase (PostgreSQL) |
| Git Operations | GitPython + GitHub REST API |
| Validation | `ruff`, `black`, Python `ast` module |
| HTTP | `httpx`, `aiofiles` |

### Frontend
| Layer | Technology |
|---|---|
| Framework | React 18 + Vite |
| Styling | Tailwind CSS |
| Icons | Lucide React |
| State | React Context + hooks |
| Charts | Recharts |

---

## Quick Start

### Prerequisites
- Python 3.11+
- Node 18+ (for UI)
- AWS account with Bedrock access (Llama 4 Maverick enabled in `us-east-1`)
- Supabase project (free tier works)

### 1. Clone & install

```bash
git clone https://github.com/your-username/spring2fast
cd spring2fast
python -m venv .venv && .venv\Scripts\activate   # Windows
# source .venv/bin/activate                       # Mac/Linux
pip install -r requirements.txt
```

### 2. Configure `.env`

```env
# LLM
GROQ_API_KEY=gsk_...
GOOGLE_API_KEY=AIza...

# AWS Bedrock (primary — required for best results)
BEDROCK_AWS_ACCESS_KEY_ID=AKIA...
BEDROCK_AWS_SECRET_ACCESS_KEY=...
BEDROCK_AWS_REGION=us-east-1

# Supabase
DB_URL=https://xxx.supabase.co
SERVICE_ROLE_KEY=eyJ...

# GitHub push (optional — enables one-click push)
GITHUB_PAT=ghp_...
```

### 3. Run the backend

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Run the frontend

```bash
cd ../spring2fast-ui
npm install && npm run dev
```

Open `http://localhost:5173` → paste a Spring Boot GitHub URL → watch the migration.

---

## How a Migration Works

1. **Paste a GitHub URL** (or upload a ZIP) in the UI
2. Spring2Fast clones the repo and scans every Java file
3. Three parallel agents run simultaneously: tech discovery, business rule extraction, component classification
4. A migration plan is generated listing every component in dependency order
5. Each component is converted by a specialised LangGraph agent using Bedrock Llama 4 Maverick
6. The output is validated, import-sanitised, and packaged
7. Push directly to GitHub or download as ZIP

---

## What Gets Migrated

| Java Spring | Python FastAPI |
|---|---|
| `@Entity` + JPA | SQLAlchemy 2.0 `Mapped[]` models |
| `JpaRepository<T,ID>` | Async SQLAlchemy repository |
| `@RestController` + `@RequestMapping` | FastAPI `APIRouter` with typed responses |
| `@Service` / `@ServiceImpl` | Python service classes with `AsyncSession` |
| Spring Security + JWT | `python-jose` + FastAPI dependency injection |
| `@RequestBody` / `@PathVariable` | Pydantic schemas + path/body params |
| `@Valid` / `@NotNull` | Pydantic field validators |
| `application.properties` | `.env` + `pydantic-settings` |
| Maven `pom.xml` | `requirements.txt` |

---

## Project Structure

```
spring2fast/
├── app/
│   ├── agents/
│   │   ├── converter_agents/     # Per-type LLM converter agents
│   │   │   ├── base.py           # Shared inner validation loop
│   │   │   ├── model.py          # Entity → SQLAlchemy model
│   │   │   ├── service.py        # @Service → Python service
│   │   │   ├── controller.py     # @RestController → APIRouter
│   │   │   └── repository.py     # JpaRepository → async repo
│   │   ├── nodes/                # LangGraph pipeline nodes
│   │   │   ├── ingest.py         # Source ingestion
│   │   │   ├── tech_discover.py  # Technology inventory
│   │   │   ├── extract_business.py
│   │   │   ├── discover_components.py
│   │   │   ├── plan.py           # Migration planner
│   │   │   ├── validate.py       # Advisory validation
│   │   │   └── assemble.py       # ZIP packaging + import sanitisation
│   │   ├── migration_subgraph/   # Code generation LangGraph subgraph
│   │   ├── graph.py              # Full pipeline DAG definition
│   │   └── state.py              # MigrationState TypedDict
│   ├── api/v1/
│   │   ├── migrate.py            # Migration job API endpoints
│   │   └── health.py             # Health + provider status
│   ├── core/
│   │   └── llm.py                # 3-tier LLM routing
│   ├── services/
│   │   ├── component_discovery_service.py
│   │   └── migration_orchestrator.py
│   ├── config.py                 # Pydantic settings
│   └── main.py                   # FastAPI app + lifespan
├── spring2fast-ui/               # React + Vite frontend
├── workspace/                    # Per-job working directories
├── requirements.txt
└── .env
```

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/migrate/github` | Start migration from GitHub URL |
| `POST` | `/api/v1/migrate/upload` | Start migration from ZIP upload |
| `GET` | `/api/v1/migrate/{job_id}/state` | Full job state (real-time polling) |
| `GET` | `/api/v1/migrate/{job_id}/result` | Download generated ZIP |
| `POST` | `/api/v1/migrate/{job_id}/push-github` | Push output to new GitHub repo |
| `GET` | `/api/v1/migrate/jobs` | List recent migration jobs |
| `GET` | `/api/v1/health` | Health + LLM provider status |

---

## License

MIT © 2026 Mohammed Musharraf
