# Spring2Fast — Reliability & Fidelity Improvement Plan

> Generalized plan to fix the root causes found across all repo types, not just petclinic.
> Every fix is grounded in a specific bug traced through the code.

---

## Root Cause: Why Only 2/6 Models Were Generated

Traced through `plan_migration.py → supervisor.py → base.py`:

The queue was built correctly — all 6 entities were in `conversion_queue`.
The problem is in `base.py → _deterministic_convert()`:

```python
# model_converter.py line 101
if "Entity" not in annotations and "@Entity" not in annotations:
    return None  # Skips deterministic path
```

Then it falls into Tier 2 (LLM). If the LLM call hits Bedrock's **rate limit or timeout**,
`base.py` catches `asyncio.CancelledError` and returns:

```python
return "# LLM call cancelled (rate limit/timeout) — manual conversion needed\npass\n"
```

This `pass` string is then written to disk and **marked as `passed=True`** because
syntax is valid! The stub-method check (`_has_stub_methods`) only runs for
`service`, `controller`, `repo` — **not `model`**. So stub model files silently pass.

The 4 missing models (`Owner`, `Pet`, `Visit`, `Vet`) got rate-limited, wrote a `pass` stub,
were marked passed, so the subgraph moved on without ever retrying them.

---

## Root Cause: Why Import Errors Every Time

Three compounding causes:

1. **`models/__init__.py` is always blank** — `config_converter_node` creates the file as
   an empty string. Any file doing `from app.models import User` fails immediately.

2. **LLM hallucinates local relative imports** — The LLM generates `from .repositories import X`
   or `from . import crud, models` (FastAPI boilerplate style) that don't match the actual
   flat package layout.

3. **`_resolve_imports` only fixes known registry entries** — If the class wasn't generated
   yet (rate-limited stub), it's not in `output_registry`, so `_resolve_imports` can't fix
   the import and instead comments it with `# FIXME`.

---

## Root Cause: Regex Class-Name Extractor Bug

```python
# component_discovery_service.py line 21
CLASS_PATTERN = re.compile(r"\bclass\s+([A-Za-z0-9_]+)\b")
```

Matches the **first** occurrence of the word `class` in the file. In `VetRepository.java`,
a keyword like `for` appears in an early context, yielding `repositories/for.py`.

---

## Fix Plan

### Fix 1 — Stub Model Detection (Highest Priority)

**File:** `app/agents/converter_agents/base.py`

Extend the inner validation loop to catch model stubs and mark them as `passed=False`:

```python
# In the inner validation loop, after syntax check, add:
if component_type == "model":
    if self._has_stub_model(code) and attempt < self.MAX_INNER_RETRIES:
        code = await self._fix_code(code,
            "INCOMPLETE: Model has no columns beyond placeholder. "
            "Add all fields from the Java @Entity source.")
        continue

@staticmethod
def _has_stub_model(code: str) -> bool:
    """True if the model file is a pass-stub or only has an id column."""
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                body_stmts = [s for s in node.body if not (
                    isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant)
                )]
                if all(isinstance(s, ast.Pass) for s in body_stmts):
                    return True
                assigns = [s for s in body_stmts if isinstance(s, ast.AnnAssign)]
                non_id = [a for a in assigns
                         if not (isinstance(a.target, ast.Name)
                                 and a.target.id in ("id", "__tablename__"))]
                if not non_id and len(assigns) <= 2:
                    return True
    except SyntaxError:
        pass
    return False
```

---

### Fix 2 — Auto-Export `models/__init__.py` After Generation

**File:** `app/agents/migration_subgraph/quality_gate.py`

After all conversions complete (when exiting the subgraph), rebuild `models/__init__.py`:

```python
def _rebuild_package_inits(output_dir: str) -> None:
    """Auto-populate __init__.py for models, schemas, services, repositories."""
    from pathlib import Path
    import re

    packages = {
        "app/models": True,       # re-export all classes
        "app/schemas": True,
        "app/services": False,    # just empty init, avoid circular imports
        "app/repositories": False,
    }
    for rel_pkg, do_exports in packages.items():
        pkg_dir = Path(output_dir) / rel_pkg
        if not pkg_dir.exists():
            continue
        exports: list[str] = []
        if do_exports:
            for py_file in sorted(pkg_dir.glob("*.py")):
                if py_file.stem == "__init__":
                    continue
                try:
                    src = py_file.read_text(encoding="utf-8", errors="ignore")
                    class_names = re.findall(
                        r"^class\s+([A-Z][A-Za-z0-9_]+)", src, re.MULTILINE
                    )
                    for cls in class_names:
                        exports.append(
                            f"from app.{rel_pkg.replace('/', '.').removeprefix('app.')}"
                            f".{py_file.stem} import {cls}"
                        )
                except Exception:
                    continue
        init_content = "\n".join(exports) + "\n" if exports else ""
        (pkg_dir / "__init__.py").write_text(init_content, encoding="utf-8")
```

Call `_rebuild_package_inits(output_dir)` at the top of the exit path in `quality_gate_node`.

---

### Fix 3 — Fix Class Name Extractor Regex

**File:** `app/services/component_discovery_service.py`

```python
# Current — matches any `class X` including loop variables
CLASS_PATTERN = re.compile(r"\bclass\s+([A-Za-z0-9_]+)\b")

# Fix — require uppercase start (Java convention), look for public/class at line start
CLASS_PATTERN = re.compile(
    r"^(?:public\s+)?(?:abstract\s+)?(?:final\s+)?class\s+([A-Z][A-Za-z0-9_]+)",
    re.MULTILINE
)
```

---

### Fix 4 — LLM-Assisted Discovery for Unclassified Files

**New file:** `app/services/llm_component_enricher.py`

Pure regex fails on:
- MyBatis / non-JPA data classes (no `@Entity`)
- Plain POJOs used as domain models
- Classes with non-standard package layouts

**Approach: Hybrid — regex fast path, LLM fallback for `category = None` files only.**
This avoids running LLM on every file (47 files × 1 LLM call = wasted tokens).

```python
class LLMComponentEnricher:
    """Use LLM to classify Java files that regex couldn't categorize."""

    CLASSIFICATION_PROMPT = """
You are analyzing Java Spring Boot source files.
For each file, determine its role. Options:
  entity   — domain object / DB model (even without @Entity if clearly a data holder)
  dto      — data transfer object (request/response body, named *Request/*Response/*Param)
  service  — business logic class
  repository — data access / persistence layer
  controller — HTTP endpoint handler
  config   — application configuration
  utility  — helper/util (skip in migration)
  unknown  — truly unclear

Return ONLY JSON: {"filename": "role", ...}

Files to classify:
{files_block}
"""

    async def enrich_unclassified(
        self,
        unclassified: list[dict],   # [{file_path, source, class_name}]
        inventory: dict,
    ) -> dict[str, list]:
        """Returns additional components merged per category."""
        if not unclassified:
            return {}
        files_block = "\n\n".join(
            f"### {f['file_path']}\n{f['source'][:600]}"
            for f in unclassified[:25]
        )
        # Call LLM, parse JSON, return {category: [component_payload, ...]}
        ...
```

**Integration:** Call inside `ComponentDiscoveryService.discover()` after the main loop,
passing any item where `_classify_component` returned `None`.

---

### Fix 5 — Live Migration Checklist in State

**The idea:** Maintain a `migration_checklist` list in `MigrationState`, built at plan time
and updated after each component. Benefits:
- Frontend gets a live task board (items update in real time via Supabase push)
- Enables pipeline resume (skip `status == "done"` items on restart)
- Makes gaps visible: `status == "failed"` items show up in the final report

**`app/agents/state.py`** — add field:
```python
migration_checklist: Annotated[NotRequired[list[dict[str, Any]]], _latest_any]
```

**Checklist item schema:**
```python
{
    "id":          "model:Owner",          # unique key: type:classname
    "type":        "model",                # model|schema|repo|service|controller|config
    "class_name":  "Owner",
    "source_file": "owner/Owner.java",
    "target_file": "app/models/owner.py",
    "status":      "pending",              # pending|in_progress|done|failed|skipped
    "tier":        None,                   # deterministic|llm|fallback|None
    "error":       None,
    "attempts":    0,
}
```

**Build in `plan_migration_node`** from the conversion queue.

**Update in `_run_converter`** after each component result:
```python
checklist = next_state.get("migration_checklist", [])
for item in checklist:
    if item["id"] == f"{component_type}:{class_name}":
        item["status"] = "done" if result.passed else "failed"
        item["tier"] = result.tier_used
        item["error"] = result.error or None
        item["attempts"] = result.attempts
        break
next_state["migration_checklist"] = checklist
```

---

### Fix 6 — Block LLM Relative Import Hallucination

**File:** `app/agents/converter_agents/base.py`

Add to `_default_system_prompt`:
```python
"CRITICAL: Never use relative imports (from . import X or from .module import X). "
"Always use absolute imports starting with 'from app.' "
"The project root package is 'app'. "
"Example: use 'from app.models.user import User', not 'from . import User'."
```

Add to `_sanitize_imports` — strip and fix relative imports post-generation:
```python
@staticmethod
def _fix_relative_imports(code: str) -> str:
    import re
    # from .something import X → from app.something import X
    code = re.sub(
        r"^from \.([a-z_]+) import (.+)$",
        r"from app.\1 import \2",
        code, flags=re.MULTILINE
    )
    # from . import X → comment (can't auto-fix without knowing layer)
    code = re.sub(
        r"^from \. import (.+)$",
        r"# FIXME: ambiguous relative import - from app.??? import \1",
        code, flags=re.MULTILINE
    )
    return code
```

Call `_fix_relative_imports` inside `_generate_with_llm` after `_strip_fences`.

---

### Fix 7 — Assembly-Time Completeness Check Against Checklist

**File:** `app/agents/nodes/validate.py`

In `validate_node`, after calling `ValidationService.validate()`, add:

```python
checklist = next_state.get("migration_checklist", [])
output_dir = next_state.get("output_dir", "")

failed_items = [item for item in checklist if item["status"] == "failed"]
missing_files = []
for item in checklist:
    if item["status"] == "done" and item.get("target_file"):
        from pathlib import Path
        if not (Path(output_dir) / item["target_file"]).exists():
            missing_files.append(item["target_file"])

if failed_items or missing_files:
    next_state["logs"] = [
        *next_state.get("logs", []),
        f"Checklist: {len(failed_items)} failed, {len(missing_files)} missing files",
        *[f"  FAILED: {i['class_name']} ({i['error']})" for i in failed_items[:5]],
        *[f"  MISSING: {f}" for f in missing_files[:5]],
    ]
```

---

## Metric → Fix Mapping

| Metric | Root Cause | Fixes |
|--------|-----------|-------|
| **SVR** 100% — keep | n/a | Maintain |
| **ISR** import errors always | Empty `__init__`, LLM relative imports | Fix 2 + Fix 6 |
| **EPR** endpoints ok | n/a | No change needed |
| **CDA** missed classes (regex, MyBatis) | Regex misses non-annotated files, `for`-keyword bug | Fix 3 + Fix 4 |
| **SFR** stub models pass silently | Rate-limit `pass` stubs marked `passed=True` | Fix 1 + Fix 7 |

---

## Implementation Order (4 Weeks)

```
Week 1 — Critical bugs (zero-risk 1-liners to small functions):
  [ ] Fix 3: Class name regex (1 line change, immediate CDA improvement)
  [ ] Fix 1: Stub model detection (prevents silent stub pass-through)
  [ ] Fix 2: Auto-export models/__init__.py (fixes ISR for every repo)

Week 2 — Import reliability:
  [ ] Fix 6: Block LLM relative import hallucination (system prompt + post-process)
  [ ] Extend Fix 2: Do same for schemas/__init__.py

Week 3 — Discovery fidelity:
  [ ] Fix 4: LLM-assisted classification for unclassified files

Week 4 — Structural observability:
  [ ] Fix 5: Migration checklist in state + frontend live task board
  [ ] Fix 7: Assembly-time checklist diff
```

---

## Notes on LLM for Discovery vs Generation

- **For generation** (converters): LLM is essential. Regex cannot write Python from Java.
- **For discovery** (classification): LLM should be a **fallback only** for files regex
  couldn't classify. Running LLM on all 47 files for discovery wastes time and tokens.
  The right breakdown: regex handles ~85% of files, LLM handles the ambiguous 15%.

- **Session memory**: Still not recommended. Context is passed explicitly per component.
  Memory would duplicate tokens across components and break retry logic.
