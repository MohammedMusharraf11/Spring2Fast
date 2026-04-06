"""Optional MCP-backed docs research integration."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from typing import Any

from app.config import settings


class MCPResearchService:
    """Queries an MCP server for documentation-search results when configured."""

    def __init__(
        self,
        *,
        enabled: bool | None = None,
        config_path: str | None = None,
        server_name: str | None = None,
        tool_name: str | None = None,
    ) -> None:
        self.enabled = settings.enable_mcp_research if enabled is None else enabled
        self.config_path = config_path or settings.mcp_server_config_path
        self.server_name = server_name or settings.mcp_docs_server_name
        self.tool_name = tool_name or settings.mcp_docs_tool_name

    def search(self, *, query: str) -> list[dict[str, str]]:
        """Synchronously query the configured MCP tool."""
        if not self.enabled:
            return []

        config_file = Path(self.config_path)
        if not config_file.exists():
            return []

        return self._run_async_in_thread(self._search_async(query=query, config_file=config_file))

    async def _search_async(self, *, query: str, config_file: Path) -> list[dict[str, str]]:
        try:
            from langchain_mcp_adapters.client import MultiServerMCPClient
        except ImportError:
            return []

        config = json.loads(config_file.read_text(encoding="utf-8"))
        client = MultiServerMCPClient(config)
        tools = await client.get_tools()
        target_tool = next(
            (tool for tool in tools if getattr(tool, "name", "") == self.tool_name or getattr(tool, "name", "").endswith(self.tool_name)),
            None,
        )
        if target_tool is None:
            return []

        result: Any = await target_tool.ainvoke({"query": query})
        if isinstance(result, list):
            return [item for item in result if isinstance(item, dict)]
        if isinstance(result, dict):
            if "results" in result and isinstance(result["results"], list):
                return [item for item in result["results"] if isinstance(item, dict)]
            return [result]
        return [{"title": "mcp_result", "url": "", "snippet": str(result), "source": "mcp"}]

    def _run_async_in_thread(self, coroutine) -> list[dict[str, str]]:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(lambda: asyncio.run(coroutine))
            return future.result(timeout=30)
