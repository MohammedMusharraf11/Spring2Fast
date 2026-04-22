"""Enum converter - Java enum to Python enum."""

from __future__ import annotations

from app.agents.tools import converter_tools as tools


def convert_enum(component: dict[str, object], output_dir: str) -> str:
    """Generate a Python Enum class from discovered enum data."""
    class_name = str(component.get("class_name", "MyEnum"))
    values = component.get("enum_values", [])
    if not isinstance(values, list) or not values:
        return ""

    lines = [
        f'"""Auto-generated Python enum for {class_name}."""',
        "",
        "from enum import Enum",
        "",
        "",
        f"class {class_name}(str, Enum):",
        f'    """Migrated from Java enum {class_name}."""',
    ]
    for value in values:
        lines.append(f'    {value} = "{value}"')

    code = "\n".join(lines) + "\n"
    output_path = f"app/models/{tools._to_snake(class_name)}.py"
    tools.write_output(output_path, code, output_dir)
    return output_path
