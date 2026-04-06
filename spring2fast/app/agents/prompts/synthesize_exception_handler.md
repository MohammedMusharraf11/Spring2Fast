You are converting a Java @ControllerAdvice / @RestControllerAdvice class to FastAPI exception handlers.

RULES:
1. Create custom exception classes that extend Python's Exception.
2. Register FastAPI exception handlers using `@app.exception_handler(CustomException)`.
3. Map common patterns:
   - @ExceptionHandler(EntityNotFoundException.class) → custom NotFoundException + handler returning 404
   - @ExceptionHandler(ValidationException.class) → handler returning 422
   - @ExceptionHandler(AccessDeniedException.class) → handler returning 403
   - @ExceptionHandler(Exception.class) → handler returning 500
4. Each handler returns a JSONResponse with {"detail": message} body.
5. Include all necessary imports: fastapi, starlette.responses, etc.
6. Export a function `register_exception_handlers(app: FastAPI)` that registers all handlers.
7. Output ONLY valid Python code. No markdown, no explanation.

### JAVA SOURCE
{java_source}

### CONTRACT
{contract_md}
