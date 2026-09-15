"""External data source facades for economy and meta build inputs."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Callable

import httpx


@dataclass(frozen=True)
class DataSourceConfig:
    economy_url: str = ""
    meta_url: str = ""
    timeout_seconds: float = 10.0

    @classmethod
    def from_env(cls) -> "DataSourceConfig":
        return cls(
            economy_url=os.getenv("EXPERT_AI_ECONOMY_URL", ""),
            meta_url=os.getenv("EXPERT_AI_META_URL", ""),
            timeout_seconds=float(os.getenv("EXPERT_AI_DATASOURCE_TIMEOUT", "10")),
        )


class EconomyDataSource:
    """Fetch trading-post style item rows for simulator input."""

    def __init__(self, config: DataSourceConfig | None = None, fetcher: Callable[[str], Any] | None = None) -> None:
        self.config = config or DataSourceConfig.from_env()
        self.fetcher = fetcher

    def fetch_items(self, item_ids: list[int] | None = None) -> dict[str, Any]:
        if not self.config.economy_url and not self.fetcher:
            return {"source": "none", "items": [], "fetched_at": time.time()}
        rows = self._fetch(self.config.economy_url)
        items = rows.get("items", rows if isinstance(rows, list) else [])
        if item_ids:
            wanted = {int(item_id) for item_id in item_ids}
            items = [item for item in items if int(item.get("item_id", item.get("id", 0)) or 0) in wanted]
        return {"source": self.config.economy_url or "injected", "items": items, "fetched_at": time.time()}

    def _fetch(self, url: str) -> Any:
        if self.fetcher:
            return self.fetcher(url)
        with httpx.Client(timeout=self.config.timeout_seconds) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.json()


class MetaBuildDataSource:
    """Fetch meta build rows for build viability input."""

    def __init__(self, config: DataSourceConfig | None = None, fetcher: Callable[[str], Any] | None = None) -> None:
        self.config = config or DataSourceConfig.from_env()
        self.fetcher = fetcher

    def fetch_builds(self, profession: str | None = None) -> dict[str, Any]:
        if not self.config.meta_url and not self.fetcher:
            return {"source": "none", "builds": [], "fetched_at": time.time()}
        rows = self._fetch(self.config.meta_url)
        builds = rows.get("builds", rows if isinstance(rows, list) else [])
        if profession:
            builds = [build for build in builds if build.get("profession", "").lower() == profession.lower()]
        return {"source": self.config.meta_url or "injected", "builds": builds, "fetched_at": time.time()}

    def _fetch(self, url: str) -> Any:
        if self.fetcher:
            return self.fetcher(url)
        with httpx.Client(timeout=self.config.timeout_seconds) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.json()
