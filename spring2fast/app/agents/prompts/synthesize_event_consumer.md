You are converting Java event listener components into fully implemented async Python consumer modules.

NON-NEGOTIABLE RULES
1. Output only valid Python code.
2. Preserve every listener method.
3. Never use `pass`, `_ = data`, TODOs, placeholder comments, or empty handlers.
4. Every consumer must deserialize the incoming message and call a real generated service method when the source code indicates one.

IMPLEMENTATION GUIDANCE
- Use `aiokafka` for Kafka listeners and `aio_pika` for RabbitMQ listeners.
- Include logging and minimal error handling around message processing.
- When a service call is identifiable from the Java listener body or contract, wire it concretely.
- If the exact service method cannot be inferred, create a clearly named processing helper that still performs message parsing and structured logging rather than leaving the body empty.
- Use async database session handling only when the migrated behavior requires it.

JAVA SOURCE
{java_source}

CONTRACT
{contract_md}

EXISTING SERVICES
{existing_services}

DOCS CONTEXT
{docs_context}

DETECTED TECHNOLOGIES
{tech_text}
