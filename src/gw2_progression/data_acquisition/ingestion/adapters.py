from __future__ import annotations

import time
from typing import Any

from gw2_progression.data_acquisition.registry.source_registry import SourceConfig


class FetchAdapter:
    """Base helper for source-specific HTTP adapters."""

    def __init__(
        self,
        *,
        client: Any,
        base_url: str,
        api_key: str = "",
        retry_attempts: int = 3,
        retry_backoff_seconds: float = 0.4,
    ) -> None:
        self.client = client
        self.base_url = base_url
        self.api_key = api_key
        self.retry_attempts = retry_attempts
        self.retry_backoff_seconds = retry_backoff_seconds

    def fetch(self, source: SourceConfig) -> dict[str, Any]:
        raise NotImplementedError

    def _source_url(self, source: SourceConfig) -> str:
        endpoint = source.endpoint or self.base_url
        if endpoint.startswith("http://") or endpoint.startswith("https://"):
            return endpoint
        return f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"

    def _headers(self, source: SourceConfig) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.api_key and source.auth_required:
            headers["Authorization"] = f"Bearer {self.api_key}"
        user_agent = source.metadata.get("user_agent")
        if user_agent:
            headers["User-Agent"] = str(user_agent)
        return headers

    def _get_with_retry(self, url: str, headers: dict[str, str] | None = None, params: dict[str, Any] | None = None) -> Any:
        last_error: Exception | None = None
        for attempt in range(max(1, self.retry_attempts)):
            try:
                return self.client.get(url, headers=headers or {}, params=params)
            except TypeError:
                return self.client.get(url, headers=headers or {})
            except Exception as e:
                last_error = e
                if attempt + 1 >= self.retry_attempts:
                    break
                time.sleep(self.retry_backoff_seconds * (attempt + 1))
        if last_error:
            raise last_error
        raise RuntimeError(f"GET failed without exception: {url}")


class GW2OfficialAdapter(FetchAdapter):
    """Official GW2 API adapter with ids=all chunk fallback."""

    def fetch(self, source: SourceConfig) -> dict[str, Any]:
        url = self._source_url(source)
        headers = self._headers(source)
        response = self._get_with_retry(url, headers)
        if getattr(response, "status_code", 200) == 400 and "ids=all" in url:
            data = self._fetch_ids_all_fallback(source, headers)
            return {
                "source_id": source.id,
                "type": source.type.value,
                "timestamp": time.time(),
                "data": data,
                "metadata": {"url": url, "mode": "real", "adapter": "gw2_official", "fallback": "ids_chunked"},
            }
        response.raise_for_status()
        return {
            "source_id": source.id,
            "type": source.type.value,
            "timestamp": time.time(),
            "data": response.json(),
            "metadata": {"url": url, "mode": "real", "adapter": "gw2_official"},
        }

    def _fetch_ids_all_fallback(self, source: SourceConfig, headers: dict[str, str]) -> list[dict[str, Any]]:
        base_url = self._source_url(source).split("?", 1)[0]
        ids_response = self._get_with_retry(base_url, headers)
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
            response = self._get_with_retry(chunk_url, headers)
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, list):
                rows.extend(payload)
            elif isinstance(payload, dict):
                rows.append(payload)
        return rows


class MediaWikiAdapter(FetchAdapter):
    """MediaWiki API adapter for GW2 Wiki content."""

    DEFAULT_PARAMS = {
        "action": "query",
        "format": "json",
        "prop": "revisions",
        "rvprop": "ids|timestamp|content",
        "rvslots": "main",
    }

    def fetch(self, source: SourceConfig) -> dict[str, Any]:
        url = source.endpoint or "https://wiki.guildwars2.com/api.php"
        params = dict(self.DEFAULT_PARAMS)
        params.update(source.metadata.get("params", {}))
        titles = source.metadata.get("titles")
        if titles and "titles" not in params:
            params["titles"] = "|".join(str(title) for title in titles)
        headers = self._headers(source)
        response = self._get_with_retry(url, headers, params=params)
        response.raise_for_status()
        return {
            "source_id": source.id,
            "type": source.type.value,
            "timestamp": time.time(),
            "data": response.json(),
            "metadata": {"url": url, "mode": "real", "adapter": "mediawiki", "params": params},
        }


class MarketTimeSeriesAdapter(GW2OfficialAdapter):
    """Official commerce adapter that stamps price/listing observations as snapshots."""

    def fetch(self, source: SourceConfig) -> dict[str, Any]:
        payload = super().fetch(source)
        observed_at = payload["timestamp"]
        data = payload.get("data", [])
        if isinstance(data, dict):
            data = [data]
        snapshots = []
        for row in data if isinstance(data, list) else []:
            if not isinstance(row, dict):
                continue
            snapshots.append({
                **row,
                "snapshot_observed_at": observed_at,
                "snapshot_source_id": source.id,
            })
        payload["data"] = snapshots
        payload["metadata"] = {**payload.get("metadata", {}), "adapter": "market_timeseries"}
        return payload
