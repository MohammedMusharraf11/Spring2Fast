# Spring2Fast — Phase 3 Implementation Plan

---

## Capability Ladder: What Migrates When

This is the clearest way to understand what each phase unlocks.

### ✅ After Phase 2 (Current State)

**You can successfully migrate:**

> A standard **single-module Spring Boot REST API** that uses JPA for persistence, Spring Security with JWT for auth, and exposes only JSON endpoints.

**Concrete profile:**
```
✅ @RestController + @RequestMapping + @PathVariable/@RequestBody
✅ @Entity with @OneToMany/@ManyToOne relationships
✅ @MappedSuperclass inheritance (fields resolved)
✅ JpaRepository<T, ID> with Spring Data method names (findByX, existsByX...)
✅ @Service / @ServiceImpl business logic
✅ @ControllerAdvice exception handlers
✅ Spring Security JWT (generates security.py stub)
✅ Single PostgreSQL or MySQL database
✅ @NotNull, @Size, @Email Bean Validation → Pydantic Field()
✅ alembic/ setup, Dockerfile, docker-compose.yml, pytest skeletons
✅ Direct GitHub push of generated project
```

**Example repos that work well today:**
- `gothinkster/spring-boot-realworld-example-app` ← already tested ✅
- `callicoder/spring-boot-rest-api-tutorial`
- `bezkoder/spring-boot-jpa-crud-rest-api`

**Example repos that partially work (some stubs):**
- `spring-projects/spring-petclinic` — MVC routes become REST, but no HTML
- Any app with many `@Service` methods containing complex business logic

---

### 🚀 After Phase 3

**You can migrate:**

> A **distributed Spring Boot system** with inter-service HTTP clients, event-driven messaging, caching layers, and complex JPA inheritance patterns — including the majority of real enterprise codebases.

**Adds on top of Phase 2:**
```
🆕 @FeignClient → async httpx service client (microservice comms)
🆕 @KafkaListener → aiokafka consumer
🆕 @RabbitListener → aio-pika consumer
🆕 @Cacheable/@CacheEvict → aiocache Redis decorators
🆕 @Scheduled → APScheduler background tasks
🆕 @Embeddable → SQLAlchemy @composite value objects
🆕 @Inheritance JOINED / SINGLE_TABLE → polymorphic SQLAlchemy
🆕 Multi-module Maven (limited cross-module awareness)
🆕 UI: Diff view, re-run single file, fidelity score
```

**Example repos that will work after Phase 3:**
- `macrozheng/mall` — large e-commerce (Feign, Redis, Kafka) ← stress test
- `halo-dev/halo` — CMS (complex JPA, scheduled tasks, event listeners)
- `Baeldung/spring-security-oauth` — OAuth2 resource server
- `spring-petclinic/spring-petclinic-microservices` — microservice version

**What still won't work after Phase 3:**
- Spring Batch (job/step/chunk processing → Celery)
- Spring WebSocket / STOMP
- Spring Cloud Gateway / Eureka service mesh
- Full OAuth2 server (auth code flow) — stubs only

---

## Phase 2 Remaining Items (Fix These First)

### P2-R1 — `alembic.ini` hardcoded SQLite URL 🟡

**Problem:** Generated `alembic.ini` has:
```ini
sqlalchemy.url = sqlite:///./app.db
```
This is wrong for PostgreSQL/MySQL projects.

**Fix in `alembic_generator.py`:**
```python
# Detect from discovered_technologies
if "postgresql" in discovered_technologies or "jpa" in discovered_technologies:
    db_url = "postgresql+asyncpg://postgres:password@localhost:5432/app"
elif "mysql" in discovered_technologies:
    db_url = "mysql+asyncmy://root:password@localhost:3306/app"
else:
    db_url = "sqlite:///./app.db"

# Write: sqlalchemy.url = %(DATABASE_URL)s
# Add to alembic env: config.set_main_option("sqlalchemy.url", os.environ.get("DATABASE_URL", fallback_url))
```

**Effort: 30 min**

---

### P2-R2 — `parse_bean_validation` annotation format mismatch 🟡

**Problem:** `converter_tools.py:parse_bean_validation()` checks:
```python
if str(annotation) == "@NotNull":  # Checks string
```
But field annotations from the discovery service are dicts:
```python
{"name": "@NotNull"}  # or {"name": "NotNull"} without @
```

**Fix:**
```python
def parse_bean_validation(fields: list[dict]) -> dict[str, dict]:
    for field in fields:
        annotations = field.get("annotations", [])
        # Normalize: handle both str and dict annotations
        ann_names = []
        for ann in annotations:
            if isinstance(ann, dict):
                ann_names.append(ann.get("name", "").lstrip("@"))
            else:
                ann_names.append(str(ann).lstrip("@"))
        # Also read pre-parsed validation dict if present
        validation = dict(field.get("validation") or {})
        # ... rest of logic using ann_names
```

**Effort: 45 min**

---

### P2-R3 — Feign clients already in categories but no converter 🟡

**Status:** `CATEGORY_RULES` already includes `"feign_clients": ["@FeignClient"]` — they're **discovered** but there's no `feign_converter.py` to convert them.

This is actually Phase 3 item 3.1 — it's ready to be built immediately.

---

### P2-R4 — Event handlers discovered but not converted 🟡

Same as above — `"event_handlers": ["@KafkaListener", "@RabbitListener"]` are discovered but unConverted. Phase 3 item 3.2.

---

## Phase 3 — Full Implementation Plan

---

## Track 1: Distributed Patterns (Week 1–2)

### 3.1 — FeignClient → `httpx` Async Service Client

**What it handles:**
```java
@FeignClient(name = "user-service", url = "${services.user.url}")
public interface UserServiceClient {
    @GetMapping("/users/{id}")
    UserDto getUser(@PathVariable Long id);
    
    @PostMapping("/orders")
    OrderDto createOrder(@RequestBody CreateOrderRequest request);
}
```

**Generates:**
```python
# app/clients/user_service_client.py
import httpx
from app.core.config import settings
from app.schemas.user import UserDto
from app.schemas.order import OrderDto, CreateOrderRequest


class UserServiceClient:
    """HTTP client for user-service — migrated from @FeignClient."""

    def __init__(self) -> None:
        self.base_url = settings.user_service_url
        self.timeout = 30.0

    async def get_user(self, id: int) -> UserDto:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(f"{self.base_url}/users/{id}")
            resp.raise_for_status()
            return UserDto.model_validate(resp.json())

    async def create_order(self, request: CreateOrderRequest) -> OrderDto:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/orders",
                json=request.model_dump(),
            )
            resp.raise_for_status()
            return OrderDto.model_validate(resp.json())
```

**New files:**
- `app/agents/converter_agents/feign_converter.py`
- `app/clients/__init__.py` in generated output

**Config generation:** Each `@FeignClient(url="${services.X.url}")` → adds `x_service_url: str` to generated `app/core/config.py`

**Effort: 1 day**

---

### 3.2 — Kafka/RabbitMQ Event Consumers

**What it handles:**
```java
@KafkaListener(topics = "orders", groupId = "order-group")
public void consumeOrder(OrderEvent event) {
    orderService.process(event);
}

@RabbitListener(queues = "payments")
public void handlePayment(PaymentMessage message) {
    paymentService.handle(message);
}
```

**Generates:**
```python
# app/consumers/order_consumer.py
import asyncio, json, logging
from aiokafka import AIOKafkaConsumer
from app.core.config import settings
from app.services.order_service import OrderService

logger = logging.getLogger(__name__)

async def consume_orders(order_service: OrderService) -> None:
    """Kafka consumer — migrated from @KafkaListener(topics='orders')."""
    consumer = AIOKafkaConsumer(
        "orders",
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id="order-group",
    )
    await consumer.start()
    try:
        async for msg in consumer:
            try:
                data = json.loads(msg.value)
                await order_service.process(data)
            except Exception as exc:
                logger.error("Failed to process order event: %s", exc)
    finally:
        await consumer.stop()
```

```python
# app/consumers/payment_consumer.py (RabbitMQ)
import aio_pika, json
from app.core.config import settings

async def consume_payments() -> None:
    """RabbitMQ consumer — migrated from @RabbitListener(queues='payments')."""
    connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    async with connection:
        channel = await connection.channel()
        queue = await channel.declare_queue("payments", durable=True)
        async for message in queue:
            async with message.process():
                data = json.loads(message.body)
                # TODO: call payment_service.handle(data)
```

**New files:**
- `app/agents/converter_agents/event_consumer_converter.py`
- Adds `aiokafka` / `aio-pika` to generated `requirements.txt` when detected

**Effort: 1.5 days**

---

### 3.3 — `@Cacheable` → `aiocache` Redis

**What it handles:**
```java
@Cacheable(value = "users", key = "#id")
public User findById(Long id) { ... }

@CacheEvict(value = "users", key = "#user.id")
public User updateUser(User user) { ... }

@CachePut(value = "users", key = "#result.id")
public User createUser(User user) { ... }
```

**Strategy:**
1. Detect `@Cacheable` methods in services
2. Wrap them with `aiocache` cache decorator in the generated Python service
3. Add Redis to `docker-compose.yml` (already handled by docker_generator)

**Generates:**
```python
from aiocache import cached, Cache
from aiocache.serializers import JsonSerializer

@cached(
    ttl=300,
    cache=Cache.REDIS,
    key_builder=lambda f, self, id: f"users:{id}",
    serializer=JsonSerializer(),
)
async def find_by_id(self, id: int) -> User | None:
    result = await self.db.execute(select(User).where(User.id == id))
    return result.scalar_one_or_none()

async def update_user(self, user: User) -> User:
    # Cache evict — migrated from @CacheEvict
    from aiocache import caches
    cache = caches.get("default")
    await cache.delete(f"users:{user.id}")
    # ... update logic
```

**New files:**
- `app/agents/converter_agents/cache_converter.py` — OR inject into service converter prompt

**Effort: 1 day**

---

### 3.4 — `@Scheduled` → APScheduler

**What it handles:**
```java
@Scheduled(fixedRate = 60000)          // every 60 seconds
public void cleanExpiredSessions() { }

@Scheduled(cron = "0 0 2 * * *")      // 2 AM daily
public void generateDailyReport() { }
```

**Generates:**
```python
# app/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

scheduler = AsyncIOScheduler()


@scheduler.scheduled_job("interval", seconds=60)
async def clean_expired_sessions() -> None:
    """Runs every 60s — migrated from @Scheduled(fixedRate=60000)."""
    # TODO: inject db session and call service
    pass


@scheduler.scheduled_job(CronTrigger.from_crontab("0 2 * * *"))
async def generate_daily_report() -> None:
    """Runs at 2 AM daily — migrated from @Scheduled(cron='0 0 2 * * *')."""
    pass
```

**Also updates `app/main.py`** to start/stop scheduler in lifespan:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.start()
    yield
    scheduler.shutdown()
```

**New files:**
- Detection in `component_discovery_service.py` — add `"scheduled_tasks"` category
- `app/agents/converter_agents/scheduler_converter.py`
- Adds `apscheduler` to generated `requirements.txt`

**Effort: 1 day**

---

## Track 2: Advanced JPA (Week 2)

### 3.5 — `@Embeddable` / `@Embedded` Value Objects

**What it handles:**
```java
@Embeddable
public class Address {
    private String street;
    private String city;
    private String zipCode;
}

@Entity
public class Owner {
    @Embedded
    private Address address;
}
```

**Currently generates:** `address` as `String` column (wrong)

**Generates instead:**
```python
# SQLAlchemy composite type
from sqlalchemy.orm import composite

class AddressComposite:
    def __init__(self, street: str, city: str, zip_code: str) -> None:
        self.street = street
        self.city = city
        self.zip_code = zip_code

class Owner(Base):
    __tablename__ = "owners"
    _street: Mapped[str] = mapped_column("address_street", String(255))
    _city: Mapped[str] = mapped_column("address_city", String(255))
    _zip_code: Mapped[str] = mapped_column("address_zip_code", String(20))
    address: AddressComposite = composite(AddressComposite, _street, _city, _zip_code)
```

**Changes:**
- Add `@Embeddable` to `CATEGORY_RULES` → new `"value_objects"` category
- Update `_deterministic_entity()` to detect `@Embedded` fields and expand them

**Effort: 1 day**

---

### 3.6 — `@Inheritance` Strategies (JOINED / SINGLE_TABLE)

**What it handles:**
```java
@Entity
@Inheritance(strategy = InheritanceType.JOINED)
public abstract class Animal { ... }

@Entity
public class Dog extends Animal { ... }
public class Cat extends Animal { ... }
```

**Generates:**
```python
# JOINED → separate tables with FK
class Animal(Base):
    __tablename__ = "animals"
    __mapper_args__ = {"polymorphic_on": "type", "polymorphic_identity": "animal"}
    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String(50))  # discriminator

class Dog(Animal):
    __tablename__ = "dogs"
    __mapper_args__ = {"polymorphic_identity": "dog"}
    id: Mapped[int] = mapped_column(ForeignKey("animals.id"), primary_key=True)

# SINGLE_TABLE → one table, all subclass columns nullable
class Animal(Base):
    __tablename__ = "animals"
    __mapper_args__ = {"polymorphic_on": "dtype"}
    dtype: Mapped[str] = mapped_column(String(50))
```

**Changes:**
- Update `_deterministic_entity()` to detect `@Inheritance` annotation
- Update model converter prompt to explain polymorphic SQLAlchemy

**Effort: 1.5 days**

---

## Track 3: Developer Experience UI (Week 3)

### 3.7 — Side-by-Side Diff View

**What it looks like:**
```
┌─────────────────────────────┬────────────────────────────────┐
│  Java Source                │  Generated Python              │
│  OwnerController.java       │  app/api/v1/endpoints/owner.py │
├─────────────────────────────┼────────────────────────────────┤
│  @GetMapping("/owners/{id}")│  @router.get("/owners/{id}")   │
│  public Owner showOwner(    │  async def get_owner(          │
│    @PathVariable Long id) { │    owner_id: int,              │
│    return ownerService      │    db: AsyncSession = Depends  │
│      .findOwnerById(id);    │  ) -> OwnerResponse:           │
│  }                          │    ...                         │
└─────────────────────────────┴────────────────────────────────┘
```

**Implementation:**
- New `DiffViewer.jsx` component — side-by-side panels with syntax highlighting
- New `GET /api/v1/migrate/{job_id}/source/{file_path}` endpoint — serve raw Java source
- New `GET /api/v1/migrate/{job_id}/output/{file_path}` endpoint — serve generated Python

**New files:**
- `spring2fast-ui/src/components/DiffViewer.jsx`
- Backend: add `source` and `output` file serving endpoints to `migrate.py`

**Effort: 1.5 days**

---

### 3.8 — Regenerate Single Component

**What it does:** User clicks a generated file → "Regenerate" button → re-runs just that converter agent without redoing the whole pipeline.

**Backend:** New endpoint:
```
POST /api/v1/migrate/{job_id}/regenerate
Body: { "component": {...} }
```
Runs the appropriate converter agent on-demand, writes the file, returns new content.

**Frontend:** "Regenerate" button on each file card in the output browser.

**Effort: 1 day**

---

### 3.9 — Migration Fidelity Score

**What it shows:**
```
Migration Fidelity Score
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Models       ████████████░  92%   (11/12 fields mapped)
Controllers  ██████████░░░  82%   (9/11 routes complete)
Services     ████████░░░░░  68%   (8/12 methods complete)
Repos        ██████████████ 100%  (6/6 queries translated)
Schemas      ███████████░░  88%   (7/8 validators mapped)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Overall      █████████░░░░  83%   Action required: 4 items
```

**How calculated:**
- Models: `all_fields` count vs generated model field count (parse with `ast`)
- Controllers: Java `@RequestMapping` count vs generated `@router.X` count
- Services: Java method count vs generated `async def` count (excluding `pass` bodies)
- Repos: query method count vs methods without `raise NotImplementedError`
- Schemas: Bean validation count vs Pydantic `Field()` with constraints count

**New files:**
- `app/agents/generators/fidelity_scorer.py`
- `spring2fast-ui/src/components/FidelityScore.jsx`
- Added to `assemble_node` output and exposed via `/state` endpoint

**Effort: 1.5 days**

---

## Implementation Priority Order

```
Week 1:
  P2-R1  alembic.ini DB URL fix       (30 min) ← Start here
  P2-R2  parse_bean_validation fix     (45 min)
  3.1    FeignClient → httpx           (1 day)
  3.2    Kafka/RabbitMQ consumers      (1.5 days)

Week 2:
  3.3    @Cacheable → aiocache         (1 day)
  3.4    @Scheduled → APScheduler      (1 day)
  3.5    @Embeddable value objects      (1 day)
  3.6    @Inheritance polymorphism      (1.5 days)

Week 3:
  3.7    Diff view UI                  (1.5 days)
  3.8    Re-run single component       (1 day)
  3.9    Fidelity score                (1.5 days)
```

---

## Effort Summary

| Item | Effort | Impact |
|---|---|---|
| P2-R1 alembic.ini fix | 30 min | 🟡 Correctness |
| P2-R2 bean validation fix | 45 min | 🟡 Schema quality |
| 3.1 Feign → httpx | 1 day | 🔵 Microservice support |
| 3.2 Kafka/Rabbit consumers | 1.5 days | 🔵 Event-driven support |
| 3.3 @Cacheable → aiocache | 1 day | 🟡 Performance layer |
| 3.4 @Scheduled → APScheduler | 1 day | 🟡 Background tasks |
| 3.5 @Embeddable | 1 day | 🟡 JPA completeness |
| 3.6 @Inheritance | 1.5 days | 🟡 JPA completeness |
| 3.7 Diff view UI | 1.5 days | ✨ Demo killer |
| 3.8 Re-run component | 1 day | ✨ UX |
| 3.9 Fidelity score | 1.5 days | ✨ Standout feature |
| **Total** | **~12 days** | |

---

## Test Repos for Phase 3 Validation

| Repo | What it validates |
|---|---|
| `spring-petclinic/spring-petclinic-microservices` | FeignClient ↔ multiple services |
| `macrozheng/mall` | Kafka + Redis + complex JPA (hardest test) |
| `halo-dev/halo` | @Scheduled, @EventListener, complex domain |
| `eugenp/tutorials` (individual modules) | Isolated tests for @Cacheable, @Embeddable |

---

## What Phase 4 Would Look Like (Preview)

After Phase 3, the remaining hard category is **true distributed infrastructure**:

- Spring Cloud (Eureka, Config Server, Zuul/Gateway) → no direct Python equivalent; generates documentation instead
- Spring Batch → Apache Airflow DAG generation or Celery chains
- Spring WebSocket → FastAPI WebSocket + connexion
- Full multi-module Maven with cross-module type sharing

Phase 4 is intentionally out of scope for now — 95% of real-world migrations don't need it.
