# Spring2Fast — DAG + Supervisor Subgraph Implementation Plan

> **4 Phases · 22 Tasks · ~8-10 days**
> Takes the pipeline from a linear chain at L5 to a parallel DAG with supervisor subgraph at L7.

---

## Target Architecture

```
                         ┌── tech_discover (fn) ──────┐
ingest (fn) ─────────────┼── biz_logic (fn) ──────────┼── merge_analysis (fn)
                         └── discover_components (fn)──┘        │
                                                                ▼
                                                    research_docs (AGENT)
                                                                │
                                                                ▼
                                                        analyze (fn) → plan (fn)
                                                                │
                                   ┌────────────────────────────▼───────────────────────────┐
                                   │         MIGRATION SUBGRAPH                             │
                                   │                                                        │
                                   │  supervisor ──┬── model_converter (AGENT)              │
                                   │       │       ├── schema_converter (AGENT)             │
                                   │       │       ├── repo_converter (AGENT)               │
                                   │       │       ├── service_converter (AGENT)            │
                                   │       │       ├── controller_converter (AGENT)         │
                                   │       │       └── config_converter (fn)                │
                                   │       │                    │                           │
                                   │       ◄── merge ──────────┘                           │
                                   │       │                                                │
                                   │  quality_gate ── pass ──► exit subgraph               │
                                   │       └── fail ──► re-route failing component         │
                                   └───────────────────────────────────────────────────────┘
                                                                │
                                                                ▼
                                                    validate (AGENT — full pipeline)
                                                                │
                                                    ┌───────────┴──────────┐
                                                    ▼                      ▼
                                             assemble (fn)         back to supervisor
                                                    │              (with error context)
                                                    ▼
                                                   END
```

### What Stays a Function (no changes)
| Node | Why |
|------|-----|
| `ingest` | Deterministic git clone / file extraction |
| `tech_discover` | Regex scan + optional LLM enrichment — single pass |
| `extract_biz_logic` | AST parsing + regex — single pass |
| `discover_components` | Annotation scanning + contract generation — single pass |
| `analyze` | Cross-referencing discovered data — computation |
| `plan` | Building target file lists — computation or single LLM call |
| `assemble` | Zip + persist — deterministic |
| `config_converter` | Settings + .env + requirements.txt — pure template |

### What Becomes an Agent (inner loops + tools)
| Node | Why |
|------|-----|
| `research_docs` | Needs to: search → fetch → read → decide if enough context → maybe search more |
| `model_converter` | Needs to: read source → read contract → generate → self-validate → fix → write |
| `schema_converter` | Same pattern as model, plus needs to reference generated models |
| `repo_converter` | Same, plus needs models for type references |
| `service_converter` | Most complex: read source + contract + models + schemas + docs → generate → check compliance |
| `controller_converter` | Needs services + schemas for correct DI and request/response types |
| `validate` | Needs to: run syntax → run lint → check imports → check structure → check compliance → classify errors |

---

## Phase 1: DAG Parallelization (2 tasks)

### Task 1.1 — Create `merge_analysis` Node
> **New file:** `app/agents/nodes/merge_analysis.py`

A simple function node that waits for all 3 parallel branches and merges their results into a unified state. LangGraph handles the fan-out/fan-in automatically — this node just receives the merged state.

```python
# The merge node receives state with all three branches' outputs already applied
# (LangGraph's state reducer handles the merge)
# It just needs to do any cross-referencing between the three outputs
def merge_analysis_node(state: MigrationState) -> MigrationState:
    # Combine tech inventory + component inventory + business rules
    # to produce a validated, cross-referenced analysis
    ...
```

**Why a separate node?** After the three branches complete, we need one place that cross-references their outputs (e.g., ensuring every component's technologies are in the tech inventory). Without this, `research_docs` would need to handle the merge.

### Task 1.2 — Rewire `graph.py` for Fan-Out / Fan-In

Replace the linear chain:
```python
# BEFORE (linear)
ingest → tech_discover → biz_logic → components → research_docs → ...

# AFTER (DAG)
ingest ──┬── tech_discover ──────┐
         ├── biz_logic ──────────┼── merge_analysis → research_docs → ...
         └── discover_components ┘
```

**Changes to `app/agents/graph.py`:**
```python
# Fan-out from ingest
builder.add_edge("ingest", "tech_discover")
builder.add_edge("ingest", "extract_business_logic")
builder.add_edge("ingest", "discover_components")

# Fan-in to merge
builder.add_edge("tech_discover", "merge_analysis")
builder.add_edge("extract_business_logic", "merge_analysis")
builder.add_edge("discover_components", "merge_analysis")

# Continue sequentially
builder.add_edge("merge_analysis", "research_docs")
```

**State challenge:** When 3 nodes run in parallel and all do `deepcopy(state)` + add their own keys, LangGraph needs to know how to merge. We need **state reducers** — annotations on the `MigrationState` that tell LangGraph how to combine parallel outputs (e.g., `list` fields use `operator.add`, `dict` fields use `merge`).

**Refactor needed:** `MigrationState` must move from a plain `TypedDict` to a LangGraph `Annotated` state with reducers:
```python
from operator import add
from typing import Annotated

class MigrationState(TypedDict):
    logs: Annotated[list[str], add]  # parallel branches' logs concatenate
    discovered_technologies: Annotated[list[str], add]  # techs from parallel branches merge
    ...
```

---

## Phase 2: Converter Agent Framework (6 tasks)

### Task 2.1 — Create Agent Tool Registry

> **New file:** `app/agents/tools/converter_tools.py`

Define the shared tools that converter agents use. Each tool is a Python function wrapped with `@tool` from LangChain:

```python
@tool
def read_java_source(file_path: str) -> str:
    """Read the raw Java source file."""

@tool
def read_contract(class_name: str, contracts_dir: str) -> str:
    """Read the .md contract for a specific class."""

@tool
def read_existing_code(layer: str, output_dir: str) -> str:
    """Read already-generated code for a layer (models, schemas, etc.)."""

@tool
def read_docs(technology: str, docs_cache: dict) -> str:
    """Read cached documentation for a Python library."""

@tool
def generate_code(prompt: str) -> str:
    """Call the LLM to generate Python code."""

@tool
def validate_syntax(code: str) -> dict:
    """Run ast.parse on code and return {valid: bool, error: str}."""

@tool
def check_imports(code: str, output_dir: str) -> dict:
    """Verify all imports resolve against generated project + requirements."""

@tool
def write_output(file_path: str, code: str, output_dir: str) -> str:
    """Write generated code to the output directory."""

@tool
def deterministic_convert(component_type: str, java_ir: dict) -> str:
    """Apply deterministic Java→Python mappings (Tier 1 conversions)."""
```

### Task 2.2 — Create the `BaseConverterAgent`

> **New file:** `app/agents/converter_agents/base.py`

An abstract base that all converter agents inherit. Handles the common loop:

```python
class BaseConverterAgent:
    """Base class for converter agents with shared tooling."""
    
    def __init__(self, tools: list, prompt_template: str):
        self.llm = get_code_model()
        self.tools = tools
        self.agent = create_react_agent(self.llm, tools, prompt_template)
    
    async def convert(self, component: dict, context: ConversionContext) -> ConversionResult:
        """Run the agent loop for a single component."""
        # 1. Build the agent input
        # 2. Run the ReAct loop (agent decides which tools to call)
        # 3. Collect the generated code + validation results
        # 4. Return structured result
```

### Task 2.3 — Model Converter Agent

> **New file:** `app/agents/converter_agents/model_converter.py`

System prompt:
```
You are a Model Converter Agent. Your job is to convert a single Java @Entity 
into a Python SQLAlchemy 2.0 model.

You have tools: read_java_source, read_contract, read_existing_code(models), 
deterministic_convert, generate_code, validate_syntax, write_output.

Strategy:
1. Read the Java entity source and its contract
2. Try deterministic conversion first (for simple entities)
3. If the entity has complex relationships or annotations, use generate_code with 
   the specialized model prompt
4. Validate syntax — if it fails, fix it
5. Write the output file
```

### Task 2.4 — Service Converter Agent

> **New file:** `app/agents/converter_agents/service_converter.py`

The most complex agent. System prompt includes:
```
You have additional tools: read_docs, read_existing_code(models), 
read_existing_code(schemas), check_imports.

Strategy:
1. Read the Java service source + contract
2. Check if it uses 3rd-party tech → if yes, read_docs for each
3. Read existing models + schemas for correct import paths
4. Generate Python service via generate_code
5. Validate syntax
6. Check imports resolve
7. If the contract has >3 business rules, ask LLM to self-check compliance
8. Write the output file
```

### Task 2.5 — Controller Converter Agent

> **New file:** `app/agents/converter_agents/controller_converter.py`

Needs `read_existing_code(services)` and `read_existing_code(schemas)` for correct DI and types.

### Task 2.6 — Schema + Repository Converter Agents

> **New files:** `app/agents/converter_agents/schema_converter.py`, `app/agents/converter_agents/repo_converter.py`

Simpler agents — schemas are mostly Pydantic field mapping, repos are Spring Data method name → SQLAlchemy query.

---

## Phase 3: Migration Supervisor + Subgraph (6 tasks)

### Task 3.1 — Define Subgraph State

> **New file:** `app/agents/migration_subgraph/state.py`

The subgraph has its OWN state, which is a subset of the main graph state plus subgraph-specific fields:

```python
class MigrationSubgraphState(TypedDict):
    """State for the migration supervisor subgraph."""
    
    # Inherited from parent
    input_dir: str
    output_dir: str
    contracts_dir: str
    discovered_technologies: list[str]
    business_rules: list[str]
    docs_context: str
    component_inventory: dict[str, list[dict[str, Any]]]
    
    # Subgraph-specific
    conversion_queue: list[dict]        # [{type: "model", component: {...}, status: "pending"}]
    completed_conversions: list[dict]   # [{type: "model", component: {...}, code: "...", passed: True}]
    failed_conversions: list[dict]      # [{type: "service", component: {...}, error: "...", attempts: 2}]
    current_conversion: dict | None     # The component currently being converted
    existing_generated_code: dict[str, str]  # Inter-layer context
    subgraph_retry_count: int
```

### Task 3.2 — Supervisor Router Node

> **New file:** `app/agents/migration_subgraph/supervisor.py`

The supervisor is a **function node** (not an agent — it doesn't need tools, just routing logic):

```python
def supervisor_node(state: MigrationSubgraphState) -> MigrationSubgraphState:
    """Pick the next component from the queue and route to the right converter."""
    queue = state["conversion_queue"]
    if not queue:
        return {**state, "current_conversion": None}  # signal to exit
    
    # Pop the next component
    next_component = queue[0]
    component_type = next_component["type"]
    
    return {
        **state,
        "current_conversion": next_component,
        "conversion_queue": queue[1:],
    }
```

The **routing** is a conditional edge:
```python
def route_to_converter(state) -> str:
    current = state.get("current_conversion")
    if not current:
        return "quality_gate"
    return f"{current['type']}_converter"  # "model_converter", "service_converter", etc.
```

### Task 3.3 — Build Conversion Queue in `plan` Node

> **Modify:** `app/agents/nodes/plan_migration.py`

Instead of `remaining_chunks = ["models", "schemas", ...]`, the plan node builds a **per-component conversion queue**:

```python
queue = []
# Models first (no dependencies)
for entity in component_inventory.get("entities", []):
    queue.append({"type": "model", "component": entity, "status": "pending"})
# Schemas second (depend on models)
for dto in component_inventory.get("dtos", []):
    queue.append({"type": "schema", "component": dto, "status": "pending"})
# Repositories third (depend on models)
for repo in component_inventory.get("repositories", []):
    queue.append({"type": "repo", "component": repo, "status": "pending"})
# Services fourth (depend on models + schemas + repos)
for svc in component_inventory.get("services", []):
    queue.append({"type": "service", "component": svc, "status": "pending"})
# Controllers last (depend on services + schemas)
for ctrl in component_inventory.get("controllers", []):
    queue.append({"type": "controller", "component": ctrl, "status": "pending"})
# Config files (deterministic, no deps)
queue.append({"type": "config", "component": {"class_name": "ProjectConfig"}, "status": "pending"})
```

**Key insight:** The queue is dependency-ordered. Models before schemas before services. The supervisor processes them in order, and each converter agent can read the already-generated code from previous conversions.

### Task 3.4 — Quality Gate Node

> **New file:** `app/agents/migration_subgraph/quality_gate.py`

After all conversions complete, the quality gate runs a quick sanity check:

```python
def quality_gate_node(state: MigrationSubgraphState) -> MigrationSubgraphState:
    """Check if all conversions passed and decide to exit or retry failures."""
    failed = state.get("failed_conversions", [])
    
    if not failed or state["subgraph_retry_count"] >= 2:
        # Exit subgraph — either all passed or we've exhausted retries
        return {**state, "status": "complete"}
    
    # Re-queue failed components for retry
    retry_queue = [
        {**f, "status": "retry", "attempts": f.get("attempts", 0) + 1}
        for f in failed if f.get("attempts", 0) < 3
    ]
    return {
        **state,
        "conversion_queue": retry_queue,
        "failed_conversions": [],
        "subgraph_retry_count": state["subgraph_retry_count"] + 1,
    }
```

### Task 3.5 — Build the Subgraph

> **New file:** `app/agents/migration_subgraph/graph.py`

```python
def build_migration_subgraph():
    builder = StateGraph(MigrationSubgraphState)
    
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("model_converter", model_converter_agent)
    builder.add_node("schema_converter", schema_converter_agent)
    builder.add_node("repo_converter", repo_converter_agent)
    builder.add_node("service_converter", service_converter_agent)
    builder.add_node("controller_converter", controller_converter_agent)
    builder.add_node("config_converter", config_converter_node)  # function, not agent
    builder.add_node("quality_gate", quality_gate_node)
    
    builder.set_entry_point("supervisor")
    
    # Supervisor routes to the appropriate converter
    builder.add_conditional_edges("supervisor", route_to_converter, {
        "model_converter": "model_converter",
        "schema_converter": "schema_converter",
        "repo_converter": "repo_converter",
        "service_converter": "service_converter",
        "controller_converter": "controller_converter",
        "config_converter": "config_converter",
        "quality_gate": "quality_gate",
    })
    
    # All converters route back to supervisor
    for converter in ["model_converter", "schema_converter", "repo_converter", 
                       "service_converter", "controller_converter", "config_converter"]:
        builder.add_edge(converter, "supervisor")
    
    # Quality gate either exits or retries
    builder.add_conditional_edges("quality_gate", should_exit_subgraph, {
        "exit": END,
        "retry": "supervisor",
    })
    
    return builder.compile()
```

### Task 3.6 — Wire Subgraph into Main Graph

> **Modify:** `app/agents/graph.py`

```python
# Replace the old "migrate" node with the subgraph
migration_subgraph = build_migration_subgraph()
builder.add_node("migrate", migration_subgraph)  # LangGraph accepts compiled graphs as nodes

# The rest stays the same
builder.add_edge("plan", "migrate")
builder.add_edge("migrate", "validate")
```

---

## Phase 4: Validation Agent + Integration (5 tasks)

### Task 4.1 — Upgrade Validate to an Agent

> **Modify:** `app/agents/nodes/validate.py`

The validation node becomes an agent that can:
- Run `validate_syntax` tool on each file
- Run `lint_check` tool
- Run `import_check` tool
- **Classify errors** into fixable vs. unfixable
- **Auto-fix trivial errors** inline (e.g., add missing `__init__.py`, fix import order)
- Return unfixable errors for the retry loop

### Task 4.2 — Upgrade Research Docs to an Agent

> **Modify:** `app/agents/nodes/research_docs.py`

Currently a single-shot function. Convert to a ReAct agent with tools:
- `search_serper(query)` — web search
- `fetch_mcp_docs(server, tool, query)` — MCP documentation fetch
- `read_url(url)` — fetch a documentation page
- `save_reference(tech, python_lib, docs_snippet)` — persist to artifacts

The agent loop: for each technology, search, read, extract the relevant API surface, decide if it has enough context. If not, search with a different query.

### Task 4.3 — State Refactoring for Subgraph Compatibility

> **Modify:** `app/agents/state.py`

Add LangGraph `Annotated` reducers for parallel fan-in:

```python
from operator import add
from typing import Annotated

class MigrationState(TypedDict):
    # Reducer: concat logs from parallel branches
    logs: Annotated[list[str], add]
    
    # Reducer: merge discovered tech lists
    discovered_technologies: Annotated[list[str], add]
    
    # Reducer: merge business rules
    business_rules: Annotated[list[str], add]
    
    # Reducer: deep-merge analysis artifacts
    analysis_artifacts: Annotated[dict[str, str], merge_dicts]
```

### Task 4.4 — Update `__init__.py` Exports

> **Modify:** `app/agents/nodes/__init__.py`

Add exports for the new `merge_analysis_node` and remove the old `generate_output_node` (replaced by subgraph).

### Task 4.5 — End-to-End Integration Test

Create a test that runs the full pipeline on a sample Spring Boot project (e.g., a simple User CRUD app with 2 entities, 2 services, 2 controllers) and verifies:
1. DAG parallelism works (analysis completes in <15s)
2. Subgraph processes all components
3. Supervisor routes correctly
4. Converter agents generate valid Python
5. Quality gate catches failures and retries
6. Validation agent produces a clean report

---

## File Impact Summary

### New Files (11)
```
app/agents/
├── tools/
│   └── converter_tools.py          # Shared agent tools
├── converter_agents/
│   ├── __init__.py
│   ├── base.py                     # BaseConverterAgent
│   ├── model_converter.py          # Model converter agent
│   ├── schema_converter.py         # Schema converter agent
│   ├── repo_converter.py           # Repository converter agent
│   ├── service_converter.py        # Service converter agent
│   └── controller_converter.py     # Controller converter agent
├── migration_subgraph/
│   ├── __init__.py
│   ├── state.py                    # Subgraph state
│   ├── supervisor.py               # Supervisor router
│   ├── quality_gate.py             # Quality gate
│   └── graph.py                    # Subgraph builder
└── nodes/
    └── merge_analysis.py           # Fan-in merge node
```

### Modified Files (6)
```
app/agents/graph.py                 # DAG + subgraph wiring
app/agents/state.py                 # Annotated reducers
app/agents/nodes/__init__.py        # Updated exports
app/agents/nodes/plan_migration.py  # Conversion queue builder
app/agents/nodes/validate.py        # Upgrade to agent
app/agents/nodes/research_docs.py   # Upgrade to agent
```

### Unchanged Files (the rest)
```
app/agents/nodes/ingest.py          # Stays a function
app/agents/nodes/tech_discover.py   # Stays a function
app/agents/nodes/extract_biz_logic  # Stays a function
app/agents/nodes/discover_components# Stays a function (already updated)
app/agents/nodes/analyze.py         # Stays a function
app/agents/nodes/assemble.py        # Stays a function
app/services/*                      # All services remain (used by agents as tools)
```

---

## Execution Order & Dependencies

```
Phase 1 (DAG) ── no dependencies, can start immediately
  ├── Task 1.1 merge_analysis node
  └── Task 1.2 rewire graph.py + state reducers

Phase 2 (Converter Agents) ── depends on Phase 1 for state shape
  ├── Task 2.1 tool registry ◄── start here
  ├── Task 2.2 BaseConverterAgent ◄── depends on 2.1
  ├── Task 2.3 model_converter ◄── depends on 2.2
  ├── Task 2.4 service_converter ◄── depends on 2.2
  ├── Task 2.5 controller_converter ◄── depends on 2.2
  └── Task 2.6 schema + repo converters ◄── depends on 2.2

Phase 3 (Supervisor Subgraph) ── depends on Phase 2 for converter agents
  ├── Task 3.1 subgraph state
  ├── Task 3.2 supervisor router
  ├── Task 3.3 plan node → conversion queue ◄── depends on 3.1
  ├── Task 3.4 quality gate
  ├── Task 3.5 build subgraph ◄── depends on 3.2 + 3.4 + Phase 2
  └── Task 3.6 wire into main graph ◄── depends on 3.5 + Phase 1

Phase 4 (Integration) ── depends on everything
  ├── Task 4.1 validate agent
  ├── Task 4.2 research_docs agent
  ├── Task 4.3 state final refactor
  ├── Task 4.4 exports update
  └── Task 4.5 integration test ◄── last
```

---

## Risk Items

| Risk | Mitigation |
|------|-----------|
| LangGraph subgraph API might differ from expected | Read LangGraph docs for `add_subgraph` / nested graph API before starting Phase 3 |
| State reducers might cause data loss during parallel fan-in | Write unit tests for `merge_analysis` node with mock parallel outputs |
| Converter agents might be slow (multiple LLM calls per component) | Add Tier 1 deterministic fast-path in each agent to skip LLM for simple components |
| Tool definitions might not match LangChain's `@tool` expected format | Test one tool in isolation before building all 9 |
| Subgraph state handoff to/from main graph might lose fields | Explicitly map fields at the subgraph entry/exit boundaries |
