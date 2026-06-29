from __future__ import annotations

import json
import os
import random
import time
from pathlib import Path
from typing import Any

import httpx

from gw2_progression.data_acquisition.ingestion.adapters import FetchAdapter, GW2OfficialAdapter, MarketTimeSeriesAdapter, MediaWikiAdapter
from gw2_progression.data_acquisition.registry.source_registry import SourceConfig, SourceType


class Fetcher:
    """Data fetcher for various source types.

    Supports three modes:
      - mock: deterministic local shape without network access
      - real: HTTP reads from the official GW2 API or source endpoint
      - replay: loads a local raw snapshot and exposes it as a source payload
    """

    def __init__(
        self,
        base_url: str = "https://api.guildwars2.com",
        mode: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float = 15.0,
        retry_attempts: int = 3,
        retry_backoff_seconds: float = 0.4,
        http_client: Any | None = None,
        replay_path: str | Path | None = None,
    ) -> None:
        self.base_url = base_url
        self.mode = mode or os.getenv("GW2_DATA_FETCH_MODE", "mock")
        self.api_key = api_key or os.getenv("GW2_API_KEY", "")
        self.timeout_seconds = timeout_seconds
        self.retry_attempts = retry_attempts
        self.retry_backoff_seconds = retry_backoff_seconds
        self.http_client = http_client
        self.replay_path = Path(replay_path or os.getenv("GW2_ACCOUNT_RAW_PATH", "")) if replay_path or os.getenv("GW2_ACCOUNT_RAW_PATH") else None

    def fetch(self, source: SourceConfig) -> dict[str, Any]:
        """Fetch data from a source."""
        replay_path = source.metadata.get("replay_path") or (str(self.replay_path) if self.replay_path else "")
        if replay_path or self.mode == "replay":
            return self._fetch_replay(source, replay_path)
        if self.mode == "real":
            return self._fetch_real(source)
        if source.type == SourceType.API:
            return self._fetch_mock_api(source)
        if source.type == SourceType.WIKI:
            return self._fetch_wiki(source)
        if source.type == SourceType.MARKET:
            return self._fetch_market(source)
        return self._fetch_generic(source)

    def _fetch_real(self, source: SourceConfig) -> dict[str, Any]:
        client = self.http_client or httpx.Client(timeout=self.timeout_seconds)
        try:
            return self._adapter_for(source, client).fetch(source)
        finally:
            if self.http_client is None and hasattr(client, "close"):
                client.close()

    def _adapter_for(self, source: SourceConfig, client: Any) -> FetchAdapter:
        adapter_name = str(source.metadata.get("adapter", "")).lower()
        kwargs = {
            "client": client,
            "base_url": self.base_url,
            "api_key": self.api_key,
            "retry_attempts": self.retry_attempts,
            "retry_backoff_seconds": self.retry_backoff_seconds,
        }
        if adapter_name == "mediawiki" or source.type == SourceType.WIKI:
            return MediaWikiAdapter(**kwargs)
        if adapter_name == "market_timeseries":
            return MarketTimeSeriesAdapter(**kwargs)
        return GW2OfficialAdapter(**kwargs)

    def _fetch_ids_all_fallback(self, client: Any, source: SourceConfig, headers: dict[str, str]) -> list[dict[str, Any]]:
        base_url = self._source_url(source).split("?", 1)[0]
        ids_response = self._get_with_retry(client, base_url, headers)
        ids_response.raise_for_status()
        ids = ids_response.json()
        if not isinstance(ids, list):
            return []
        chunk_size = int(source.metadata.get("chunk_size", 200))
        max_items = int(source.metadata.get("max_items", 0) or 0)
        selected_ids = ids[:max_items] if max_items > 0 else ids
        rows: list[dict[str, Any]] = []
        for start in range(0, len(selected_ids), chunk_size):
            chunk = selected_ids[start : start + chunk_size]
            chunk_url = f"{base_url}?ids={','.join(str(item_id) for item_id in chunk)}"
            response = self._get_with_retry(client, chunk_url, headers)
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, list):
                rows.extend(payload)
            elif isinstance(payload, dict):
                rows.append(payload)
        return rows

    def _get_with_retry(self, client: Any, url: str, headers: dict[str, str]) -> Any:
        last_error: Exception | None = None
        for attempt in range(max(1, self.retry_attempts)):
            try:
                return client.get(url, headers=headers)
            except Exception as e:
                last_error = e
                if attempt + 1 >= self.retry_attempts:
                    break
                time.sleep(self.retry_backoff_seconds * (attempt + 1))
        if last_error:
            raise last_error
        raise RuntimeError(f"GET failed without exception: {url}")

    def _fetch_replay(self, source: SourceConfig, replay_path: str) -> dict[str, Any]:
        path = Path(replay_path)
        if not path.exists():
            raise FileNotFoundError(f"Replay source not found: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        replay_key = source.metadata.get("replay_key")
        data = payload.get(replay_key, payload) if replay_key else payload
        return {
            "source_id": source.id,
            "type": source.type.value,
            "timestamp": float(payload.get("collected_at", time.time())) if isinstance(payload, dict) else time.time(),
            "data": data,
            "metadata": {"path": str(path), "mode": "replay", "replay_key": replay_key},
        }

    def _source_url(self, source: SourceConfig) -> str:
        endpoint = source.endpoint or self.base_url
        if endpoint.startswith("http://") or endpoint.startswith("https://"):
            return endpoint
        return f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"

    def _fetch_mock_api(self, source: SourceConfig) -> dict[str, Any]:
        if "wallet" in source.endpoint:
            return {
                "source_id": source.id,
                "type": "api",
                "timestamp": time.time(),
                "data": [
                    {"id": 1, "value": random.randint(100, 5000), "name": "Gold"},
                    {"id": 2, "value": random.randint(1000, 50000), "name": "Karma"},
                    {"id": 4, "value": random.randint(10, 500), "name": "Gems"},
                ],
            }
        if "achievements" in source.endpoint:
            return {
                "source_id": source.id,
                "type": "api",
                "timestamp": time.time(),
                "data": [
                    {"id": a, "name": f"Achievement_{a}", "done": True, "reps": 1}
                    for a in random.sample(range(1000, 9999), random.randint(5, 20))
                ],
            }
        if "items" in source.endpoint:
            return {
                "source_id": source.id,
                "type": "api",
                "timestamp": time.time(),
                "data": [
                    {"id": i, "name": f"Item_{i}", "level": random.randint(1, 80), "rarity": random.choice(["basic", "fine", "rare", "exotic"])}
                    for i in random.sample(range(10000, 99999), random.randint(10, 30))
                ],
            }
        return {"source_id": source.id, "type": "api", "timestamp": time.time(), "data": []}

    def _fetch_wiki(self, source: SourceConfig) -> dict[str, Any]:
        return {
            "source_id": source.id,
            "type": "wiki",
            "timestamp": time.time(),
            "data": {
                "pages": [
                    {"title": "Crafting", "sections": ["Materials", "Disciplines", "Recipes"]},
                    {"title": "Economy", "sections": ["Trading Post", "Currency", "Farming"]},
                ],
                "recipes": [
                    {"id": 1, "output": "Mithril Ingot", "disciplines": ["armorsmith", "weaponsmith"]},
                    {"id": 2, "output": "Bolt of Damask", "disciplines": ["tailor"]},
                ],
            },
        }

    def _fetch_market(self, source: SourceConfig) -> dict[str, Any]:
        items = ["Mithril Ore", "Elder Plank", "Mystic Coin", "Ectoplasm", "T6 Mat"]
        return {
            "source_id": source.id,
            "type": "market",
            "timestamp": time.time(),
            "data": {
                item: {
                    "buy_price": round(random.uniform(10, 500), 2),
                    "sell_price": round(random.uniform(15, 600), 2),
                    "supply": random.randint(100, 50000),
                    "demand": random.randint(50, 10000),
                }
                for item in items
            },
        }

    def _fetch_generic(self, source: SourceConfig) -> dict[str, Any]:
        return {"source_id": source.id, "type": "generic", "timestamp": time.time(), "data": {}}
