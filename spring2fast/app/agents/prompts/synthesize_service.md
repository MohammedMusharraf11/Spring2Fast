You are converting a Java @Service class to a Python service class.

CRITICAL: Preserve EVERY piece of business logic. This is the most important layer.

RULES:
1. Map the Spring service to a plain Python class with constructor injection:
   ```python
   class UserService:
       def __init__(self, db: AsyncSession) -> None:
           self.db = db
           self.user_repo = UserRepository(db)
   ```
2. Use the EXISTING REPOSITORIES as dependencies. Import them from `app.repositories.{snake_name}`.
3. Use the EXISTING MODELS for type annotations. Import from `app.models.{snake_name}`.
4. Use the EXISTING SCHEMAS for input/output types. Import from `app.schemas.{snake_name}`.
5. Translate ALL Java business logic:
   - if/else branches → Python if/else (every branch!)
   - try/catch → try/except with specific exception types
   - Stream/Optional → list comprehensions / `or None`
   - @Transactional → the db session handles transactions
   - Lombok @Slf4j logging → Python `import logging; logger = logging.getLogger(__name__)`
6. Raise FastAPI HTTPException for error cases:
   - EntityNotFoundException → HTTPException(status_code=404)
   - ValidationException → HTTPException(status_code=422)
   - AccessDenied → HTTPException(status_code=403)
7. Make methods async if they do DB operations.
8. If the service uses third-party tech (Redis, Kafka, etc.), use the PYTHON DOCS CONTEXT below.
9. Output ONLY valid Python code. No markdown, no explanation.

### JAVA SOURCE
{java_source}

### BUSINESS LOGIC CONTRACT (must satisfy ALL rules listed here)
{contract_md}

### PYTHON DOCS CONTEXT (for third-party libraries)
{docs_context}

### EXISTING MODELS (import from these)
{existing_models}

### EXISTING SCHEMAS (import from these)
{existing_schemas}

### EXISTING REPOSITORIES (import and use as dependencies)
{existing_repos}

### TECHNOLOGIES
{tech_text}
