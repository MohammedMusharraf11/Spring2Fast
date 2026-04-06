You are converting a Java Spring Data JPA Repository interface to a Python repository class using SQLAlchemy 2.0.

RULES:
1. Convert standard Spring Data methods:
   - findById(id) → get by primary key using `session.get(Model, id)`
   - findAll() → `session.execute(select(Model)).scalars().all()`
   - save(entity) → `session.add(entity); session.commit(); session.refresh(entity)`
   - deleteById(id) → `session.execute(delete(Model).where(Model.id == id)); session.commit()`
   - existsById(id) → `session.get(Model, id) is not None`
   - count() → `session.execute(select(func.count()).select_from(Model)).scalar()`
2. Convert custom query methods (Spring Data naming convention):
   - findByEmail(email) → `session.execute(select(Model).where(Model.email == email)).scalar_one_or_none()`
   - findByStatusAndType(s, t) → `session.execute(select(Model).where(Model.status == s, Model.type == t))`
   - findByNameContaining(name) → `session.execute(select(Model).where(Model.name.contains(name)))`
   - findByCreatedAtAfter(date) → `select(Model).where(Model.created_at > date)`
   - findAllByOrderByCreatedAtDesc() → `select(Model).order_by(Model.created_at.desc())`
3. Convert @Query annotations:
   - JPQL → SQLAlchemy query equivalent
   - Native SQL → `text()` queries
4. Use async session pattern with `AsyncSession` if the project uses async.
5. Accept session as constructor parameter for dependency injection.
6. Import everything needed at the top.
7. Output ONLY valid Python code. No markdown, no explanation.

### JAVA SOURCE
{java_source}

### REPOSITORY CONTRACT
{contract_md}

### ALREADY GENERATED MODELS (use these exact class names)
{existing_code}
