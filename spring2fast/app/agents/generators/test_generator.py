"""pytest skeleton generation for migrated projects."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


@dataclass(slots=True)
class TestGenerationResult:
    generated_files: list[str]


class TestGenerator:
    """Generate smoke-test skeletons for services and endpoints."""

    def generate(self, *, output_dir: str, component_inventory: dict[str, list[dict]]) -> TestGenerationResult:
        output_root = Path(output_dir)
        tests_root = output_root / "tests"
        tests_root.mkdir(parents=True, exist_ok=True)
        generated: list[str] = []

        init_path = tests_root / "__init__.py"
        init_path.write_text("", encoding="utf-8")
        generated.append("tests/__init__.py")

        for service in component_inventory.get("services", []):
            class_name = str(service.get("class_name", "Service"))
            module_name = self._to_snake(class_name)
            file_path = tests_root / f"test_{module_name}.py"
            file_path.write_text(
                "\n".join(
                    [
                        "import pytest",
                        "",
                        "",
                        "@pytest.mark.asyncio",
                        f"async def test_{module_name}_smoke() -> None:",
                        f"    \"\"\"TODO: instantiate and exercise {class_name}.\"\"\"",
                        "    assert True",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            generated.append(f"tests/test_{module_name}.py")

        for controller in component_inventory.get("controllers", []):
            class_name = str(controller.get("class_name", "Controller"))
            route_name = self._to_snake(class_name.removesuffix("Controller"))
            file_path = tests_root / f"test_{route_name}_api.py"
            file_path.write_text(
                "\n".join(
                    [
                        "import pytest",
                        "from httpx import ASGITransport, AsyncClient",
                        "",
                        "from app.main import app",
                        "",
                        "",
                        "@pytest.mark.asyncio",
                        f"async def test_{route_name}_endpoint_smoke() -> None:",
                        '    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:',
                        f'        response = await client.get("/api/v1/{route_name.replace("_", "-")}")',
                        "    assert response.status_code in (200, 404, 405)",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            generated.append(f"tests/test_{route_name}_api.py")

        return TestGenerationResult(generated_files=generated)

    def _to_snake(self, name: str) -> str:
        return re.sub(r"(?<!^)(?=[A-Z])", "_", name.removesuffix("Impl")).lower()
