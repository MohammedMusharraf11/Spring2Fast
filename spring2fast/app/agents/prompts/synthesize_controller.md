You are converting a Java @RestController to a FastAPI APIRouter.

RULES:
1. Create a module-level `router = APIRouter()`.
2. Map EVERY endpoint precisely:
   - @GetMapping("/{id}") → @router.get("/{id}")
   - @PostMapping → @router.post(status_code=201)
   - @PutMapping("/{id}") → @router.put("/{id}")
   - @DeleteMapping("/{id}") → @router.delete("/{id}", status_code=204)
   - @PatchMapping("/{id}") → @router.patch("/{id}")
3. Map parameters:
   - @PathVariable Long id → id: int
   - @RequestBody XxxDto → body: XxxCreate (use Create schema for POST, Update schema for PUT)
   - @RequestParam String name → name: str = Query(...)
   - @RequestParam(required=false) → name: str | None = Query(default=None)
   - @PageableDefault → skip: int = 0, limit: int = 20
4. Use dependency injection for database sessions:
   ```python
   @router.get("/{id}")
   async def get_item(id: int, db: AsyncSession = Depends(get_db)):
       service = ItemService(db)
       return service.get_by_id(id)
   ```
5. Import the service class from `app.services.{snake_name}`.
6. Import schemas from `app.schemas.{snake_name}`.
7. Import `get_db` from `app.db.session`.
8. SECURITY: If the Java controller has @PreAuthorize, @Secured, or security annotations:
   - Add `current_user: str = Depends(get_current_user)` parameter
   - Import `get_current_user` from `app.core.security`
   - Pass current_user to service methods that need it
9. Return types: use Response schemas for GET, Create schemas for POST responses.
10. Output ONLY valid Python code. No markdown, no explanation.

### JAVA SOURCE
{java_source}

### CONTRACT
{contract_md}

### EXISTING SERVICES (import from these)
{existing_services}

### EXISTING SCHEMAS (import from these)
{existing_schemas}

### SECURITY DETECTED
{security_context}
