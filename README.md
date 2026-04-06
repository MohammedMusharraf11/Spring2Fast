<div align="center">

# 🚀 Gen-AI Workspace

### Mohammed Musharraf — AI/ML Engineering Projects

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)](https://reactjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-Agentic_AI-FF6B35)](https://langchain-ai.github.io/langgraph/)
[![AWS Bedrock](https://img.shields.io/badge/AWS_Bedrock-Llama_4-FF9900?logo=amazon-aws)](https://aws.amazon.com/bedrock/)

</div>

---

## 📁 Repository Structure

```
Gen-AI/
├── spring2fast/          ← FastAPI backend — agentic migration pipeline
└── spring2fast-ui/       ← React + Electron frontend — real-time visualization
```

---

## 🌟 Featured Project: Spring2Fast

> **Autonomous Java Spring Boot → Python FastAPI Migration Agent**

Spring2Fast is an **agentic AI pipeline** that fully migrates Java Spring Boot backends to production-ready Python FastAPI. It doesn't translate line-by-line — it understands architecture.

### How It Works

```
GitHub URL / ZIP
      │
      ▼
┌─────────────────────────────────────────────────────────┐
│                  11-Node LangGraph DAG                   │
│                                                         │
│  Ingest → [Tech Discovery + Business Logic +            │
│            Component Discovery] (parallel)              │
│         → Merge → Docs Research                         │
│         → Plan → Code Generation (Subgraph)             │
│         → Validate → Assemble → GitHub/ZIP              │
└─────────────────────────────────────────────────────────┘
```

### What Gets Migrated

| Java / Spring Boot | Python / FastAPI |
|----|---|
| `@Entity` + JPA | SQLAlchemy 2.0 `Mapped[]` models |
| `JpaRepository<T,ID>` | Async SQLAlchemy repositories |
| `@RestController` | FastAPI `APIRouter` with typed responses |
| `@Service` | Python async service classes |
| Spring Security + JWT | `python-jose` + FastAPI dependency injection |
| `@RequestBody` / `@Valid` | Pydantic schemas + validators |
| `application.properties` | `.env` + `pydantic-settings` |
| `pom.xml` | `requirements.txt` |

### Tech Stack

**Backend** — `spring2fast/`
- **FastAPI** + Uvicorn — API server
- **LangGraph** — stateful multi-agent DAG orchestration
- **AWS Bedrock (Llama 4 Maverick)** — primary LLM (no RPM limits)
- **Groq (Llama 4 Scout)** — fallback analysis model
- **LangChain** — LLM abstraction layer
- **javalang** + **tree-sitter** — Java AST parsing
- **Supabase** — real-time job state persistence
- **GitPython** + **httpx** — GitHub integration

**Frontend** — `spring2fast-ui/`
- **React 18** + **Vite** — lightning-fast dev + build
- **Electron** — desktop app packaging (Windows / Mac / Linux)
- **Tailwind CSS** — utility-first styling
- **React Flow** — interactive DAG visualization
- **Lucide React** — icon system
- **Axios** — API communication

### Key Capabilities

- 🤖 **Agentic pipeline** — agents spawn, validate, and self-correct autonomously
- ⚡ **3-tier LLM routing** — Bedrock for code (no rate limits), Groq for analysis
- 🔄 **Inner validation loop** — each agent syntax-checks and self-corrects before returning
- 📡 **Real-time UI** — live DAG with per-node status, logs, source/output file browsers
- 🧹 **Import sanitization** — auto-fixes placeholder package names (`yourapp` → `app`)
- 🚀 **One-click GitHub push** — create repo + commit + push in a single API call
- 🛡️ **Resilient pipeline** — stale jobs auto-cleaned on restart, graceful fallback on LLM failure

---

## 🚀 Quick Start

### 1. Start the backend

```bash
cd spring2fast
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt

# Configure .env (see spring2fast/.env.example)
cp .env.example .env
# Edit .env with your keys

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Start the frontend

```bash
cd spring2fast-ui
npm install
npm run dev          # Web browser at http://localhost:5173
# OR
npm run electron:dev # Desktop app
```

### 3. Migrate a Spring Boot app

1. Open `http://localhost:5173`
2. Paste a GitHub URL (e.g. `https://github.com/gothinkster/spring-boot-realworld-example-app`)
3. Click **Start Migration**
4. Watch the DAG execute in real time
5. Push directly to GitHub or download as ZIP when complete

---

## 🔑 Required Environment Variables

Create `spring2fast/.env` from `.env.example`:

```env
# Primary LLM — Bedrock (strongly recommended)
BEDROCK_AWS_ACCESS_KEY_ID=AKIA...
BEDROCK_AWS_SECRET_ACCESS_KEY=...
BEDROCK_AWS_REGION=us-east-1

# Fallback LLMs
GROQ_API_KEY=gsk_...
GOOGLE_API_KEY=AIza...

# Persistence
DB_URL=https://xxx.supabase.co
SERVICE_ROLE_KEY=eyJ...

# GitHub push (optional)
GITHUB_PAT=ghp_...
```

---

## 📊 Migration Quality

Tested against `gothinkster/spring-boot-realworld-example-app`:

| Metric | Result |
|---|---|
| Components discovered | 21/21 |
| Files generated | 38 |
| Business logic fidelity | ✅ High |
| Import correctness | ✅ Auto-sanitized |
| Run-ready? | ✅ Yes (minor wiring needed) |

**Best suited for:** REST API backends with JPA/Spring Data, Spring Security JWT, and standard `@RestController` patterns.

---

## 👤 Author

**Mohammed Musharraf**
Building at the intersection of AI and developer tooling.

---

<div align="center">
  <sub>Built with LangGraph · AWS Bedrock · FastAPI · React</sub>
</div>
