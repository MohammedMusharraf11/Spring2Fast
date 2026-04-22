"""Utility to load system prompts from the prompts directory."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent / "prompts"


@lru_cache(maxsize=32)
def load_system_prompt(name: str) -> str:
    """Load a system prompt .md file by name (without extension).

    Example: load_system_prompt("system_tech_discovery")
    """
    path = PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"System prompt not found: {path}")
    return path.read_text(encoding="utf-8").strip()
