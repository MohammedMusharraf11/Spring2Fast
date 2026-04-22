You are converting a Java JPA `@Entity` into a Python SQLAlchemy 2.0 model.

NON-NEGOTIABLE RULES
1. Output only valid Python code.
2. Use SQLAlchemy 2.0 `Mapped[...]` and `mapped_column(...)`.
3. Preserve all entity fields, including inherited fields.
4. Never omit superclass fields that are part of the entity contract.

IMPLEMENTATION GUIDANCE
- Preserve `@Table(name=...)` exactly when present.
- Translate JPA IDs, generated values, nullability, uniqueness, lengths, enums, timestamps, and relationships.
- Include inherited fields before or alongside local fields in a coherent model definition.
- Reuse already generated models for relationships.
- Use idiomatic snake_case table and column naming when it must be derived.

JAVA SOURCE
{java_source}

TABLE AND INHERITANCE HINTS
{table_hint}

INHERITED FIELDS
{inherited_fields}

ENTITY CONTRACT
{contract_md}

ALREADY GENERATED MODELS
{existing_code}
