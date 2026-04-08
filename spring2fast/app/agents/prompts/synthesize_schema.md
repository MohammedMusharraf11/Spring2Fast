You are converting a Java DTO/request/response class into Pydantic v2 schemas.

NON-NEGOTIABLE RULES
1. Output only valid Python code.
2. Generate create, update, and response schemas when the Java type represents request/response payload data.
3. Preserve bean validation constraints in Pydantic fields.
4. Do not leave fields untyped or use placeholder defaults.

IMPLEMENTATION GUIDANCE
- Use `BaseModel`, `ConfigDict`, and `Field`.
- Preserve required vs optional semantics.
- Map validation annotations such as not-null, size, email, regex, min, and max.
- Reuse already generated models only for typing references when helpful.
- Keep field names idiomatic and consistent with the generated API surface.

JAVA SOURCE
{java_source}

FIELD VALIDATION CONSTRAINTS
{validation_context}

CONTRACT
{contract_md}

EXISTING MODELS
{existing_code}
