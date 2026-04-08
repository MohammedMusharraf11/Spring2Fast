You are converting a Java Spring `@RestController` or `@Controller` into a FastAPI `APIRouter`.

NON-NEGOTIABLE RULES
1. Output only valid Python code.
2. Preserve every Java endpoint as a FastAPI route.
3. Never use `pass`, TODOs, placeholder comments, `return None`, or stub handlers.
4. Every route must call a real service method and return a concrete response.
5. If the source is MVC-style and returns views/templates, redesign it as REST and return the underlying data as JSON or typed response models.
6. Use dependency injection with `AsyncSession = Depends(get_db)` and security dependencies when needed.

IMPLEMENTATION GUIDANCE
- Create `router = APIRouter()`.
- Map request methods and paths faithfully.
- Convert `@PathVariable`, `@RequestParam`, `@RequestBody`, and request headers into idiomatic FastAPI parameters.
- Reuse existing generated services and schemas exactly by class name when possible.
- If Spring Security is present, add `current_user: str = Depends(get_current_user)` only to protected routes.
- For delete endpoints, return `None` only when the deletion itself is implemented and the route uses an appropriate status code.
- For MVC handlers, extract the data assembled into the model and return it in a JSON structure or schema response.

JAVA SOURCE
{java_source}

CONTRACT
{contract_md}

EXISTING SERVICES
{existing_services}

EXISTING SCHEMAS
{existing_schemas}

SECURITY CONTEXT
{security_context}
