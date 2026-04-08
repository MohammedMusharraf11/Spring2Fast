# Fix Plan: SFS 43.1% → 90%+ 

## Root Cause Diagnosis

```
SVR  100% ✅  — Files parse correctly        (structure is fine)
ICR  100% ✅  — Imports resolve              (registry works)
SFS   43% ❌  — 28/65 methods preserved     (bodies are stubs)
SFS  100% ✅  — 21/21 classes present       (discovery works)
CDA   N/A ⚠️  — No ground truth file        (never generated)
```

**The problem is NOT class generation. It's method bodies.**

Every `pass`, `return None`, `raise NotImplementedError`, or `# TODO` inside a method body = **SFS miss**. 

Two causes:
1. **Prompts are too vague** — service prompt is 53 lines, feign/scheduler prompts are 3 lines. LLM generates skeleton, not implementation.
2. **Inner validation loop only checks syntax/imports** — never checks if method bodies are stubs.

---

## Fix 1 — Rewrite All LLM Prompts (Most Impactful)

Replace every `.md` prompt file. Write them now below.

---

## Fix 2 — Add Method Completeness Check to Inner Loop

**File:** `app/agents/converter_agents/base.py`

After syntax check, add:

```python
def _has_stub_methods(self, code: str) -> list[str]:
    """Return list of method names whose bodies are pure stubs."""
    import ast
    stubs = []
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = node.body
        # Strip docstring
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
            body = body[1:]
        if not body:
            stubs.append(node.name)
            continue
        # Body is only pass, return None, or raise NotImplementedError
        is_stub = all(
            isinstance(stmt, ast.Pass)
            or (isinstance(stmt, ast.Return) and (stmt.value is None or (isinstance(stmt.value, ast.Constant) and stmt.value.value is None)))
            or (isinstance(stmt, ast.Raise) and stmt.exc and "NotImplementedError" in ast.unparse(stmt.exc))
            for stmt in body
        )
        if is_stub:
            stubs.append(node.name)
    return stubs
```

**Then in the validation loop (after syntax check passes):**
```python
stub_methods = self._has_stub_methods(code)
if stub_methods and component_type in ("service", "controller", "repo"):
    # Force LLM retry with explicit stub list
    error = (
        f"INCOMPLETE: These methods have empty/stub bodies: {stub_methods}. "
        "Re-implement them with real logic from the Java source. "
        "Every method MUST have a real implementation body."
    )
    raise ValueError(error)
```

This makes stub-heavy files fail validation → trigger LLM self-correction retry.

---

## Fix 3 — Generate Ground Truth File (Fixes CDA N/A)

**File:** `app/services/component_discovery_service.py`

Add at end of `discover()`, after writing `03-component-inventory.md`:

```python
# Write ground truth JSON for CDA scoring
ground_truth = {
    "entities": [c["class_name"] for c in components.get("entities", [])],
    "services": [c["class_name"] for c in components.get("services", [])],
    "repositories": [c["class_name"] for c in components.get("repositories", [])],
    "controllers": [c["class_name"] for c in components.get("controllers", [])],
    "dtos": [c["class_name"] for c in components.get("dtos", [])],
    "feign_clients": [c["class_name"] for c in components.get("feign_clients", [])],
    "event_handlers": [c["class_name"] for c in components.get("event_handlers", [])],
    "scheduled_tasks": [c["class_name"] for c in components.get("scheduled_tasks", [])],
    "total_methods": sum(
        len(c.get("methods", [])) for cat in components.values() for c in cat
    ),
}
ground_truth_path = artifact_dir / "ground_truth.json"
import json
ground_truth_path.write_text(json.dumps(ground_truth, indent=2), encoding="utf-8")
```

---

## Fix 4 — Wire Sandbox API Endpoint

**File:** `app/api/v1/migrate.py` — add at end:

```python
# ── Sandbox Testing ───────────────────────────────────────────────────────────
import json as _json

async def _run_sandbox_background(job_id: str, output_dir: str, artifacts_dir: str) -> None:
    from app.agents.generators.sandbox_tester import SandboxTester
    tester = SandboxTester()
    await tester.run(job_id=job_id, output_dir=output_dir, artifacts_dir=artifacts_dir)


@router.post("/{job_id}/sandbox")
async def run_sandbox_test(job_id: str, background_tasks: BackgroundTasks):
    """Spin up the generated app and smoke-test all endpoints."""
    job = _get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.get("status") != "completed":
        raise HTTPException(status_code=400, detail="Job must be completed before sandbox testing")

    workspace = Path(settings.workspace_dir) / job_id
    output_dir = str(workspace / "output")
    artifacts_dir = str(workspace / "artifacts")

    background_tasks.add_task(_run_sandbox_background, job_id, output_dir, artifacts_dir)
    return {
        "status": "sandbox_started",
        "job_id": job_id,
        "poll_url": f"/api/v1/migrate/{job_id}/sandbox-report",
    }


@router.get("/{job_id}/sandbox-report")
async def get_sandbox_report(job_id: str):
    """Get sandbox test results (poll until status != running)."""
    workspace = Path(settings.workspace_dir) / job_id
    status_path = workspace / "artifacts" / "_sandbox_status.json"
    report_path = workspace / "artifacts" / "sandbox_report.json"

    if report_path.exists():
        return _json.loads(report_path.read_text(encoding="utf-8"))
    if status_path.exists():
        return _json.loads(status_path.read_text(encoding="utf-8"))
    return {"status": "not_started"}
```

---

## Fix 5 — Phase 3 `_build_llm_prompt` Unpack Fix

**Files:** `feign_converter.py`, `event_consumer_converter.py`, `scheduler_converter.py`

All three have:
```python
def _build_llm_prompt(self, **kwargs) -> str:
    return "Convert..."  # drops all context
```

Fix each to:
```python
def _build_llm_prompt(self, *, java_source: str, contract: str,
                       existing_code: dict, discovered_technologies: list,
                       docs_context: str, component: dict) -> str:
    template_path = self._get_prompt_template_path()
    template = template_path.read_text(encoding="utf-8") if template_path.exists() else "..."
    return template.replace("{java_source}", java_source).replace("{contract_md}", contract)
```

---

## Effort + Priority

| Fix | File(s) | Time | SFS Impact |
|---|---|---|---|
| **Rewrite all prompts** | `app/agents/prompts/*.md` | 1h | +35–40% |
| **Stub method checker** | `base.py` | 45 min | +10–15% |
| **Ground truth file** | `component_discovery_service.py` | 20 min | Fixes CDA |
| **Sandbox API endpoint** | `migrate.py` | 30 min | Enables sandbox |
| **Phase 3 `_build_llm_prompt`** | 3 converter files | 20 min | Phase 3 quality |

**Total: ~3 hours → Expected SFS 85–95%**
