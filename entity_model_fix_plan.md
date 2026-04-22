# Implementation Plan: Fix Missing Entity Models (100% SFS)

## The Problem

After migration, `models/` contains **only 5 enum files** — zero ORM entity models:
```
app/models/
├── attendance_status.py   ← ✅ Enum (correct)
├── event_status.py        ← ✅ Enum (correct)
├── registration_status.py ← ✅ Enum (correct)
├── student_status.py      ← ✅ Enum (correct)
├── user_role.py           ← ✅ Enum (correct)
├── user.py                ← ❌ MISSING
├── admin.py               ← ❌ MISSING
├── student.py             ← ❌ MISSING
├── organizer.py           ← ❌ MISSING
├── event.py               ← ❌ MISSING
├── notification.py        ← ❌ MISSING
└── registration.py        ← ❌ MISSING
```

## Root Cause Analysis — This is NOT an LLM problem

> [!IMPORTANT]
> **Using a better LLM will NOT fix this.** The entity models fail at **Tier 1 (deterministic conversion)**, which never touches the LLM at all. The code path is:

```
model_converter._deterministic_convert()
    → checks: "Entity" in annotations?
    → YES for User, Admin, etc.
    → calls super()._deterministic_convert()
    → calls converter_tools.deterministic_convert("model", java_ir)
    → calls _deterministic_entity(cls)
    → generates SQLAlchemy model — SHOULD work
```

**But wait** — look at `model_converter.py:102`:
```python
return super()._deterministic_convert(
    component=component,
    java_ir=java_ir,
    java_source=java_source,
)
```

The `super()._deterministic_convert()` in `BaseConverterAgent` is **abstract** — it raises `NotImplementedError`! The `ModelConverterAgent` overrides `_deterministic_convert`, finds `@Entity` in annotations, then **calls its own parent** which doesn't have the entity-specific logic. The actual entity generator (`_deterministic_entity` in `converter_tools.py`) is only callable through `converter_tools.deterministic_convert()`, not through the base class method.

**So what actually happens:**
1. `ModelConverterAgent._deterministic_convert()` is called
2. It finds `@Entity` in annotations → proceeds
3. Calls `super()._deterministic_convert()` — but the base class method just returns `None` (or fails silently)
4. Returns `None` → falls through to LLM tier
5. LLM sees an entity Java source → generates... something? Or the output gets overwritten by the enum file

The **real** bug: the model_converter calls `super()._deterministic_convert()` instead of `converter_tools.deterministic_convert()`. It delegates back to the base class which has no model-specific logic.

## The Fix — 3 Changes

### Fix 1: `model_converter.py` — Call the right function (5 min)

```diff
     def _deterministic_convert(
         self,
         *,
         component: dict[str, Any],
         java_ir: dict[str, Any],
         java_source: str,
     ) -> str | None:
         classes = java_ir.get("classes", [])
         if not classes:
             return None

         cls = classes[0]
         annotations = [a.get("name", "") for a in cls.get("annotations", [])]
         if "Entity" not in annotations:
             return None

         cls["all_fields"] = component.get("all_fields") or cls.get("fields", [])
         cls["table_name"] = component.get("table_name")
         cls["inheritance_strategy"] = component.get("inheritance_strategy")
-        return super()._deterministic_convert(
-            component=component,
-            java_ir=java_ir,
-            java_source=java_source,
-        )
+        from app.agents.tools import converter_tools as tools
+        return tools.deterministic_convert("model", java_ir)
```

This routes entities to `_deterministic_entity()` which has the full SQLAlchemy column mapping, relationship handling, and inheritance support.

### Fix 2: Enum vs Entity Disambiguation (10 min)

The discovery service correctly separates enums from entities in the inventory:
- **Entities:** User, Admin, Student, Organizer, Event, Registration, Notification (have `@Entity`)
- **Enums:** UserRole, EventStatus, etc. (Java `enum` keyword)

But the `plan_migration.py` queues both as `type: "model"`. When the enum hits the model_converter, it fails the `"Entity" in annotations` check at line 96, returns `None`, falls through to the LLM, and the LLM generates a Python `enum`. This part **works correctly** — enums DO get generated.

The problem is the entity files from the same converter either:
- Get written but then **overwritten** by the config_converter which generates `__init__.py` files
- Or simply don't get written because `super()._deterministic_convert()` returns `None`

**No change needed here** — Fix 1 resolves this.

### Fix 3: `_deterministic_repository` Uses Sync Session (5 min)

The deterministic repository generator at `converter_tools.py:277-304` uses:
```python
from sqlalchemy.orm import Session  # ← SYNC
```

But the services expect `AsyncSession`. Fix:

```diff
-    f"from sqlalchemy.orm import Session\n"
-    f"from sqlalchemy import select\n"
+    f"from sqlalchemy.ext.asyncio import AsyncSession\n"
+    f"from sqlalchemy import select\n"
...
-    f"    def __init__(self, db: Session) -> None:\n"
+    f"    def __init__(self, db: AsyncSession) -> None:\n"
...
-    f"    def get_by_id(self, id: int) -> {model_name} | None:\n"
-    f"        return self.db.get({model_name}, id)\n\n"
+    f"    async def get_by_id(self, id: int) -> {model_name} | None:\n"
+    f"        return await self.db.get({model_name}, id)\n\n"
-    f"    def get_all(self) -> list[{model_name}]:\n"
-    f"        return list(self.db.execute(select({model_name})).scalars().all())\n\n"
+    f"    async def get_all(self) -> list[{model_name}]:\n"
+    f"        result = await self.db.execute(select({model_name}))\n"
+    f"        return list(result.scalars().all())\n\n"
-    f"    def save(self, entity: {model_name}) -> {model_name}:\n"
-    f"        self.db.add(entity)\n"
-    f"        self.db.commit()\n"
-    f"        self.db.refresh(entity)\n"
-    f"        return entity\n\n"
+    f"    async def save(self, entity: {model_name}) -> {model_name}:\n"
+    f"        self.db.add(entity)\n"
+    f"        await self.db.commit()\n"
+    f"        await self.db.refresh(entity)\n"
+    f"        return entity\n\n"
-    f"    def delete(self, entity: {model_name}) -> None:\n"
-    f"        self.db.delete(entity)\n"
-    f"        self.db.commit()\n"
+    f"    async def delete(self, entity: {model_name}) -> None:\n"
+    f"        await self.db.delete(entity)\n"
+    f"        await self.db.commit()\n"
```

---

## Expected Impact

| Fix | Files | Time | Impact |
|---|---|---|---|
| Fix 1: Entity converter routing | `model_converter.py` | 5 min | **7 missing entity models generated** |
| Fix 2: N/A (already correct) | — | 0 min | — |
| Fix 3: Async repositories | `converter_tools.py` | 5 min | Repos compatible with async services |

### After Applying These Fixes

| Metric | Current | Expected |
|---|---|---|
| SVR | 100% | **100%** |
| ICR | ~85% | **~98%** (model imports resolve) |
| SFS (Methods) | 87.9% | **90%+** |
| SFS (Classes) | 76.9% | **100%** (all 26 classes generated) |
| CDA | 100% | **100%** |
| App Startable? | ❌ No | ✅ Yes |

---

## Why a Better LLM Won't Help

The entity model generation is **100% deterministic** — it uses `_deterministic_entity()` which maps Java fields to SQLAlchemy columns with a hardcoded type table. The LLM is never involved. The bug is a simple **routing error**: `super()._deterministic_convert()` instead of `tools.deterministic_convert("model", java_ir)`.

A better LLM would only help with:
- Service/controller method body quality (already 87.9% ✅)
- Complex JPQL query translation  
- Business logic edge cases

The missing models are a **plumbing bug**, not an intelligence problem.
