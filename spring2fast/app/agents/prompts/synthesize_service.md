You are converting a Java Spring `@Service` class into a fully implemented async Python service class for FastAPI.

NON-NEGOTIABLE RULES
1. Output only valid Python code.
2. Preserve every Java method as a Python method unless it is a trivial getter/setter that is already represented by the model or schema.
3. Never use `pass`, `return None` as a placeholder, `raise NotImplementedError`, ellipsis, TODO comments, or placeholder comments inside method bodies.
4. Every method must contain real logic derived from the Java source, the contract, and the already-generated repositories/models/schemas.
5. Use async SQLAlchemy patterns and await repository or session operations.
6. If Java throws domain exceptions, convert them to appropriate `HTTPException` or domain-specific Python exceptions with real messages.

IMPLEMENTATION GUIDANCE
- Build a concrete service class with `__init__(self, db: AsyncSession)`.
- Reuse generated repositories when repository access is needed.
- Preserve control flow, validation branches, authorization checks, loops, stream transformations, and transaction semantics.
- Translate Java collections and stream pipelines into normal Python loops/comprehensions with actual return values.
- When data is created or updated, commit and refresh through the async session or repository implementation.
- When an entity is not found, raise `HTTPException(status_code=404, detail=...)`.
- When access is denied, raise `HTTPException(status_code=403, detail=...)`.
- If caching annotations are present, preserve the intent in code structure and comments only when necessary, but do not leave the method body empty.

OUTPUT SHAPE
- Include imports.
- Define exactly one service class for the source component.
- Keep method names idiomatic Python snake_case.
- Return concrete values that match the method behavior.

JAVA SOURCE
{java_source}

BUSINESS LOGIC CONTRACT
{contract_md}

PYTHON DOCS CONTEXT
{docs_context}

EXISTING MODELS
{existing_models}

EXISTING SCHEMAS
{existing_schemas}

EXISTING REPOSITORIES
{existing_repos}

CACHE CONTEXT
{cache_context}

DETECTED TECHNOLOGIES
{tech_text}
