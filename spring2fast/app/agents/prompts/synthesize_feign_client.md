You are converting a Java `@FeignClient` interface into a fully implemented async Python `httpx` client.

NON-NEGOTIABLE RULES
1. Output only valid Python code.
2. Preserve every interface method.
3. Never use `pass`, TODOs, or placeholder comments.
4. Every method must perform a real HTTP request with `httpx.AsyncClient`.

IMPLEMENTATION GUIDANCE
- Create a concrete client class.
- Use `settings.<service>_url` or the detected config key for the base URL.
- Map HTTP method, path variables, query parameters, request bodies, and headers from the Java source.
- Call `response.raise_for_status()` and return parsed JSON or nothing for void-like deletes.
- Keep method names snake_case and parameter names Pythonic.

JAVA SOURCE
{java_source}

CONTRACT
{contract_md}

EXISTING CLIENTS
{existing_code}

DOCS CONTEXT
{docs_context}

DETECTED TECHNOLOGIES
{tech_text}
