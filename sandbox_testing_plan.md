# Sandbox Testing — Implementation Plan

## What It Does

After migration completes:
1. Spin up the generated FastAPI app in a **subprocess** (uvicorn, random port)
2. Swap the DB to **SQLite in-memory** — no real database needed
3. Hit `GET /openapi.json` to discover every route automatically
4. Fire one HTTP request per route with **synthetic payloads**
5. Collect status codes + response snippets
6. Kill the process → return a **sandbox report**

---

## Verdict Logic

| Status Code | Verdict | Meaning |
|---|---|---|
| 2xx | ✅ **pass** | Endpoint works end-to-end |
| 401 / 403 | ⚠️ **warn** | Auth required — expected without token |
| 404 | ⚠️ **warn** | Synthetic ID not in DB — expected |
| 422 | ⚠️ **warn** | Schema mismatch — payload incomplete |
| 5xx | ❌ **fail** | Server crash — broken import / logic |
| Timeout / no response | ❌ **fail** | App didn't start or hung |

---

## Architecture

```
User clicks "Run Sandbox"
        │
        ▼
POST /api/v1/migrate/{job_id}/sandbox
        │
        ├── 1. Patch env: DATABASE_URL=sqlite+aiosqlite:///./sandbox.db
        ├── 2. subprocess: uvicorn app.main:app --port {random}
        ├── 3. Poll GET /openapi.json until healthy (max 45s)
        ├── 4. Parse openapi.json → extract all paths + methods
        ├── 5. Build synthetic payloads from schema $refs
        ├── 6. httpx: fire one request per route
        ├── 7. Kill subprocess, delete sandbox.db
        └── 8. Return SandboxReport JSON
```

---

## Files to Create / Edit

| File | Action | What |
|---|---|---|
| `app/agents/generators/sandbox_tester.py` | **Create** | Core test runner |
| `app/api/v1/migrate.py` | **Edit** | Add `POST /{job_id}/sandbox` endpoint |
| `spring2fast-ui/src/pages/JobStatusPage.jsx` | **Edit** | Add Sandbox panel + results table |

---

## Sandbox Report Shape

```json
{
  "job_id": "abc123",
  "startup_ok": true,
  "startup_error": null,
  "total_routes": 12,
  "passed": 7,
  "warned": 4,
  "failed": 1,
  "score_pct": 58,
  "duration_s": 14.3,
  "results": [
    {
      "method": "GET",
      "path": "/api/v1/articles",
      "status_code": 200,
      "verdict": "pass",
      "latency_ms": 34.2,
      "response_snippet": "{\"articles\": [], \"count\": 0}"
    },
    {
      "method": "POST",
      "path": "/api/v1/users/login",
      "status_code": 500,
      "verdict": "fail",
      "error": "ImportError: cannot import name 'UserService'",
      "latency_ms": 12.1
    }
  ]
}
```

---

## UI Panel

```
┌─────────────────────────────────────────────────────┐
│  🧪 Sandbox Test                    [Run Sandbox]   │
├──────────┬──────────┬──────────┬────────────────────┤
│ 7 passed │ 4 warned │ 1 failed │  Score: 58%  14.3s │
├──────────┴──────────┴──────────┴────────────────────┤
│ ✅ GET  /api/v1/articles               200   34ms   │
│ ✅ POST /api/v1/users                  201   51ms   │
│ ⚠️ POST /api/v1/users/login            401   12ms   │
│ ⚠️ GET  /api/v1/articles/{slug}        404   9ms    │
│ ❌ POST /api/v1/profiles/{u}/follow    500   13ms   │
│    └─ ImportError: cannot import 'ProfileService'   │
└─────────────────────────────────────────────────────┘
```

---

## What It Can and Cannot Validate

| ✅ Can validate | ❌ Cannot validate |
|---|---|
| App starts without import errors | Actual business logic correctness |
| All routes are reachable | DB query results |
| Schema validation works (no 422 crash) | Auth token behavior |
| No 500s on GET routes | Kafka / Redis consumers |
| Endpoint response structure | Complex multi-step flows |

> The score is a **structural health check**, not a functional test. A 100% score means the app boots and all routes respond — not that the logic is correct.

---

## Effort

| Task | Time |
|---|---|
| `sandbox_tester.py` — core runner | 4h |
| API endpoint + background job | 2h |
| UI panel + results table | 3h |
| **Total** | **~1.5 days** |

---

## Key Design Decisions

- **SQLite shim** — no external DB required. Generated app uses `DATABASE_URL` env var; sandbox overrides it to SQLite. Tables created via `Base.metadata.create_all()` call injected at startup.
- **OpenAPI-driven** — route discovery is automatic, no regex parsing of source files needed.
- **Async subprocess** — sandbox runs in a background task; frontend polls `GET /{job_id}/sandbox-status`.
- **Score metric** — `passed / total_routes * 100`. Warns count as 0.5 toward the denominator penalty.
