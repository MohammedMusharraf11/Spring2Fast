"""Runtime sandbox testing for generated FastAPI projects."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import random
import socket
import sys
import time
from typing import Any

import httpx


class SandboxTester:
    """Spin up a generated app, probe routes, and persist a sandbox report."""

    def __init__(self, *, startup_timeout_s: float = 45.0) -> None:
        self.startup_timeout_s = startup_timeout_s

    async def run(self, *, job_id: str, output_dir: str, artifacts_dir: str) -> dict[str, Any]:
        started_at = time.perf_counter()
        output_root = Path(output_dir)
        artifacts_root = Path(artifacts_dir)
        artifacts_root.mkdir(parents=True, exist_ok=True)
        status_path = artifacts_root / "_sandbox_status.json"
        report_path = artifacts_root / "sandbox_report.json"
        sandbox_db = output_root / "sandbox.db"

        status_path.write_text(json.dumps({"job_id": job_id, "status": "running"}), encoding="utf-8")

        port = self._find_free_port()
        env = os.environ.copy()
        env["DATABASE_URL"] = "sqlite+aiosqlite:///./sandbox.db"
        env["PYTHONPATH"] = str(output_root)
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            cwd=str(output_root),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        startup_ok = False
        startup_error = None
        results: list[dict[str, Any]] = []
        openapi: dict[str, Any] = {}

        try:
            openapi = await self._wait_for_openapi(port)
            startup_ok = True
            results = await self._probe_routes(port=port, openapi=openapi)
        except Exception as exc:
            startup_error = str(exc)
        finally:
            await self._shutdown_process(proc)
            if sandbox_db.exists():
                sandbox_db.unlink(missing_ok=True)

        passed = sum(1 for item in results if item["verdict"] == "pass")
        warned = sum(1 for item in results if item["verdict"] == "warn")
        failed = sum(1 for item in results if item["verdict"] == "fail")
        total_routes = len(results)
        score_pct = int((passed / total_routes) * 100) if total_routes else 0
        report = {
            "job_id": job_id,
            "startup_ok": startup_ok,
            "startup_error": startup_error,
            "total_routes": total_routes,
            "passed": passed,
            "warned": warned,
            "failed": failed,
            "score_pct": score_pct,
            "duration_s": round(time.perf_counter() - started_at, 2),
            "results": results,
        }
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        status_path.write_text(json.dumps({"job_id": job_id, "status": "completed", "report_path": str(report_path)}), encoding="utf-8")
        return report

    async def _wait_for_openapi(self, port: int) -> dict[str, Any]:
        deadline = time.perf_counter() + self.startup_timeout_s
        async with httpx.AsyncClient(timeout=5.0) as client:
            while time.perf_counter() < deadline:
                try:
                    response = await client.get(f"http://127.0.0.1:{port}/openapi.json")
                    response.raise_for_status()
                    return response.json()
                except Exception:
                    await asyncio.sleep(1.0)
        raise TimeoutError("Sandbox app did not expose /openapi.json in time")

    async def _probe_routes(self, *, port: int, openapi: dict[str, Any]) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        schemas = openapi.get("components", {}).get("schemas", {})
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}", timeout=10.0) as client:
            for path, operations in openapi.get("paths", {}).items():
                if path in {"/openapi.json", "/docs", "/redoc"}:
                    continue
                for method, operation in operations.items():
                    started = time.perf_counter()
                    request_kwargs = self._build_request_kwargs(path=path, method=method, operation=operation, schemas=schemas)
                    try:
                        response = await client.request(method.upper(), request_kwargs["path"], **request_kwargs["kwargs"])
                        snippet = response.text[:240]
                        verdict = self._verdict_for_status(response.status_code)
                        results.append(
                            {
                                "method": method.upper(),
                                "path": path,
                                "status_code": response.status_code,
                                "verdict": verdict,
                                "latency_ms": round((time.perf_counter() - started) * 1000, 1),
                                "response_snippet": snippet,
                            }
                        )
                    except Exception as exc:
                        results.append(
                            {
                                "method": method.upper(),
                                "path": path,
                                "status_code": None,
                                "verdict": "fail",
                                "latency_ms": round((time.perf_counter() - started) * 1000, 1),
                                "error": str(exc),
                            }
                        )
        return results

    def _build_request_kwargs(
        self,
        *,
        path: str,
        method: str,
        operation: dict[str, Any],
        schemas: dict[str, Any],
    ) -> dict[str, Any]:
        rendered_path = path
        kwargs: dict[str, Any] = {}
        for parameter in operation.get("parameters", []):
            name = parameter.get("name", "value")
            location = parameter.get("in")
            schema = parameter.get("schema", {})
            value = self._sample_scalar(schema)
            if location == "path":
                rendered_path = rendered_path.replace("{" + name + "}", str(value))
            elif location == "query":
                kwargs.setdefault("params", {})[name] = value
            elif location == "header":
                kwargs.setdefault("headers", {})[name] = str(value)

        body_schema = (
            operation.get("requestBody", {})
            .get("content", {})
            .get("application/json", {})
            .get("schema")
        )
        if body_schema and method.lower() in {"post", "put", "patch"}:
            kwargs["json"] = self._sample_from_schema(body_schema, schemas)

        return {"path": rendered_path, "kwargs": kwargs}

    def _sample_from_schema(self, schema: dict[str, Any], schemas: dict[str, Any]) -> Any:
        if "$ref" in schema:
            ref_name = schema["$ref"].split("/")[-1]
            return self._sample_from_schema(schemas.get(ref_name, {}), schemas)
        schema_type = schema.get("type")
        if schema_type == "object" or "properties" in schema:
            payload = {}
            properties = schema.get("properties", {})
            required = set(schema.get("required", []))
            for name, prop in properties.items():
                if required and name not in required:
                    continue
                payload[name] = self._sample_from_schema(prop, schemas)
            return payload
        if schema_type == "array":
            return [self._sample_from_schema(schema.get("items", {}), schemas)]
        return self._sample_scalar(schema)

    def _sample_scalar(self, schema: dict[str, Any]) -> Any:
        schema_type = schema.get("type")
        schema_format = schema.get("format")
        if schema.get("enum"):
            return schema["enum"][0]
        if schema_format == "email":
            return "sandbox@example.com"
        if schema_type == "integer":
            return 1
        if schema_type == "number":
            return 1.0
        if schema_type == "boolean":
            return True
        return "sample"

    def _verdict_for_status(self, status_code: int) -> str:
        if 200 <= status_code < 300:
            return "pass"
        if status_code in {401, 403, 404, 422}:
            return "warn"
        return "fail"

    async def _shutdown_process(self, proc: asyncio.subprocess.Process) -> None:
        if proc.returncode is not None:
            return
        proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), timeout=10.0)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()

    def _find_free_port(self) -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            sock.listen(1)
            return int(sock.getsockname()[1])
