You are converting a Java `@ControllerAdvice` or `@RestControllerAdvice` into FastAPI exception handler registration code.

NON-NEGOTIABLE RULES
1. Output only valid Python code.
2. Create real exception types and real FastAPI exception handlers.
3. Do not emit placeholder handlers or commentary.

IMPLEMENTATION GUIDANCE
- Export a `register_exception_handlers(app: FastAPI)` function.
- Map not found, validation, access denied, and generic exceptions to appropriate status codes.
- Use `JSONResponse` with a consistent `detail` payload.
- Preserve any custom exception naming and semantics visible in the Java source.

JAVA SOURCE
{java_source}

CONTRACT
{contract_md}
