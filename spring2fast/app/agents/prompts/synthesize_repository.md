You are converting a Java Spring Data repository into a fully implemented async SQLAlchemy 2.0 repository.

NON-NEGOTIABLE RULES
1. Output only valid Python code.
2. Preserve every declared repository method.
3. Never use `pass`, `raise NotImplementedError`, TODOs, or placeholder comments.
4. Every method must execute real SQLAlchemy queries and return real values.
5. Use `AsyncSession` and await all database operations.

IMPLEMENTATION GUIDANCE
- Create a repository class with `__init__(self, db: AsyncSession)`.
- Use `select`, `delete`, `update`, `exists`, `func`, and `text` when appropriate.
- Prefer precise SQLAlchemy expressions over vague helper wrappers.
- Use the translated query hints as a starting point, but refine them to match the Java source exactly.
- For Spring Data derived queries, infer filters, ordering, existence checks, counts, and delete operations from the method name.
- For `@Query`, translate JPQL or native SQL into real SQLAlchemy code.
- Return `scalar_one_or_none`, `scalar_one`, `list(result.scalars().all())`, or `list(result.mappings().all())` as appropriate.

JAVA SOURCE
{java_source}

TRANSLATED QUERY HINTS
{query_hints}

REPOSITORY CONTRACT
{contract_md}

ALREADY GENERATED MODELS
{existing_code}
