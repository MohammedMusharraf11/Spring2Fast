"""Test bootstrap helpers."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def disable_live_llm_calls():
    """Keep unit tests deterministic even when local API keys are configured."""
    with (
        patch("app.core.llm.get_chat_model", return_value=None),
        patch("app.services.technology_llm_enricher.get_chat_model", return_value=None),
        patch("app.services.business_logic_llm_enricher.get_chat_model", return_value=None),
        patch("app.services.docs_research_llm_enricher.get_chat_model", return_value=None),
        patch("app.services.planning_llm_enricher.get_chat_model", return_value=None),
    ):
        yield
