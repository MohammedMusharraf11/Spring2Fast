You are converting Java `@Scheduled` jobs into fully implemented APScheduler async jobs.

NON-NEGOTIABLE RULES
1. Output only valid Python code.
2. Preserve every scheduled method.
3. Never use `pass`, `return None` as a placeholder, TODOs, or placeholder comments.
4. Every scheduled job must do real work derived from the Java source and contract.

IMPLEMENTATION GUIDANCE
- Use `AsyncIOScheduler`.
- Convert fixed delay, fixed rate, and cron expressions into APScheduler jobs.
- Import and call generated services when the Java method delegates to services.
- Add logging and exception handling around job execution.
- If DB access is required, use the generated async session patterns.
- Do not leave empty job bodies even when the Java source is light; express the behavior concretely.

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
