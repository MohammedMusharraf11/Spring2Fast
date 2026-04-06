You are converting a Java DTO/Request/Response class to Pydantic v2 BaseModel schemas.

RULES:
1. Generate THREE schema variants per DTO:
   - `{ClassName}Create` — for POST requests. All required fields, no `id`.
   - `{ClassName}Update` — for PUT/PATCH requests. All fields Optional except `id`.
   - `{ClassName}Response` — for API responses. Includes `id`, timestamps, `model_config = ConfigDict(from_attributes=True)`.
2. Use Pydantic v2 syntax: `from pydantic import BaseModel, ConfigDict, Field`.
3. Map Java types precisely:
   - String → str
   - Long/Integer/int → int
   - Double/Float/double/float → float
   - Boolean/boolean → bool
   - LocalDateTime/Date → datetime (from datetime import datetime)
   - BigDecimal → Decimal (from decimal import Decimal)
   - List<X> → list[X]
   - Set<X> → set[X]
   - Map<K,V> → dict[K,V]
   - Optional/nullable fields → T | None = None
4. Preserve validation annotations:
   - @NotNull/@NotBlank → required field (no default)
   - @Size(min=N,max=M) → Field(min_length=N, max_length=M)
   - @Email → EmailStr (from pydantic import EmailStr)
   - @Min(N)/@Max(N) → Field(ge=N) / Field(le=N)
5. Import from generated models if the schema references an entity.
6. Output ONLY valid Python code. No markdown, no explanation.

### JAVA SOURCE
{java_source}

### CONTRACT
{contract_md}

### EXISTING MODELS (for type references)
{existing_code}
