"""Serper search integration for dynamic docs discovery."""

from __future__ import annotations

from typing import Any

import httpx

from app.config import settings


class SerperSearchService:
    """Queries the Serper search API when configured."""

    SEARCH_URL = "https://google.serper.dev/search"

    def __init__(self, *, api_key: str | None = None, enabled: bool | None = None) -> None:
        self.api_key = api_key or settings.serper_api_key
        self.enabled = settings.enable_serper_search if enabled is None else enabled

    def search(self, *, query: str, num_results: int = 5) -> list[dict[str, str]]:
        """Return normalized Serper search results."""
        if not self.enabled or not self.api_key:
            return []

        response = httpx.post(
            self.SEARCH_URL,
            headers={
                "X-API-KEY": self.api_key,
                "Content-Type": "application/json",
            },
            json={"q": query, "num": min(max(num_results, 1), 10)},
            timeout=15,
        )
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
        items = payload.get("organic", [])
        return [
            {
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "snippet": item.get("snippet", ""),
                "source": "serper_search",
            }
            for item in items
            if item.get("link")
        ]
