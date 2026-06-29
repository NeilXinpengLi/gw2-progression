from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


@dataclass
class IngestResult:
    source_id: str
    source_type: str
    status: str
    raw_data: dict[str, Any] = field(default_factory=dict)
    record_count: int = 0
    error: str | None = None
    elapsed_ms: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_type": self.source_type,
            "status": self.status,
            "record_count": self.record_count,
            "error": self.error,
            "elapsed_ms": round(self.elapsed_ms, 2),
            "timestamp": self.timestamp,
            "has_data": bool(self.raw_data),
        }


class DataIngestion:
    def __init__(self, api_key: str | None = None, gw2radar_path: str | None = None):
        self._api_key = api_key
        self._gw2radar_path = gw2radar_path
        self._cache: dict[str, tuple[float, Any]] = {}
        self._cache_ttl = 300.0

    def ingest(self, source_type: str, **params: Any) -> IngestResult:
        start = time.perf_counter()
        source_id = params.get("source_id", f"{source_type}:{uuid.uuid4().hex[:8]}")

        handler = self._get_handler(source_type)
        if handler is None:
            elapsed = (time.perf_counter() - start) * 1000
            return IngestResult(
                source_id=source_id,
                source_type=source_type,
                status="unsupported",
                error=f"no handler for source type: {source_type}",
                elapsed_ms=elapsed,
            )

        cache_key = f"{source_type}:{json.dumps(params, sort_keys=True, default=str)}"
        if cache_key in self._cache:
            cached_at, cached_data = self._cache[cache_key]
            if time.monotonic() - cached_at < self._cache_ttl:
                elapsed = (time.perf_counter() - start) * 1000
                return IngestResult(
                    source_id=source_id,
                    source_type=source_type,
                    status="cached",
                    raw_data=cached_data,
                    record_count=len(cached_data) if isinstance(cached_data, list) else 1,
                    elapsed_ms=elapsed,
                )

        try:
            raw_data = handler(**params)
            self._cache[cache_key] = (time.monotonic(), raw_data)
            record_count = self._count_records(raw_data)
            elapsed = (time.perf_counter() - start) * 1000
            return IngestResult(
                source_id=source_id,
                source_type=source_type,
                status="ok",
                raw_data=raw_data,
                record_count=record_count,
                elapsed_ms=elapsed,
            )
        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            return IngestResult(
                source_id=source_id,
                source_type=source_type,
                status="error",
                error=str(e),
                elapsed_ms=elapsed,
            )

    def ingest_multi(self, sources: list[dict]) -> list[IngestResult]:
        return [self.ingest(s["type"], **s.get("params", {})) for s in sources]

    def _get_handler(self, source_type: str) -> Callable | None:
        handlers: dict[str, Callable] = {
            "gw2_api": self._handle_gw2_api,
            "gw2_wallet": self._handle_gw2_api,
            "gw2_inventory": self._handle_gw2_api,
            "gw2_characters": self._handle_gw2_api,
            "gw2_achievements": self._handle_gw2_api,
            "gw2_recipes": self._handle_gw2_recipes,
            "gw2radar": self._handle_gw2radar,
            "local_file": self._handle_local_file,
            "local_json": self._handle_local_json,
            "static": self._handle_static,
        }
        return handlers.get(source_type)

    def _handle_gw2_api(self, **params: Any) -> dict[str, Any]:
        from gw2_progression.analyzer import fetch_all

        api_key = params.get("api_key") or self._api_key
        if not api_key:
            raise ValueError("GW2 API key required")
        endpoint = params.get("endpoint", "all")

        if endpoint == "wallet":
            data = asyncio.run(fetch_all(api_key, endpoints=["wallet"]))
        elif endpoint == "inventory":
            data = asyncio.run(fetch_all(api_key, endpoints=["bank", "materials"]))
        elif endpoint == "characters":
            data = asyncio.run(fetch_all(api_key, endpoints=["characters"]))
        elif endpoint == "achievements":
            data = asyncio.run(fetch_all(api_key, endpoints=["achievements"]))
        else:
            data = asyncio.run(fetch_all(api_key))

        return data._asdict() if hasattr(data, "_asdict") else {"account": str(data), "items": [], "wallet": []}

    def _handle_gw2_recipes(self, **params: Any) -> dict[str, Any]:
        import aiohttp

        async def _fetch():
            async with aiohttp.ClientSession() as session:
                async with session.get("https://api.guildwars2.com/v2/recipes") as resp:
                    recipe_ids = await resp.json()
                async with session.get(
                    f"https://api.guildwars2.com/v2/recipes?ids={','.join(str(i) for i in recipe_ids[:200])}"
                ) as resp:
                    return await resp.json()

        try:
            data = asyncio.run(_fetch())
        except RuntimeError:
            loop = asyncio.new_event_loop()
            data = loop.run_until_complete(_fetch())
            loop.close()
        return {"recipes": data or []}

    def _handle_gw2radar(self, **params: Any) -> dict[str, Any]:
        try:
            from gw2radar.db.repositories import GraphRepository
            from gw2radar.graph.graph_builder import GraphData

            db_path = params.get("db_path") or self._gw2radar_path
            repo = GraphRepository(db_path) if db_path else GraphRepository()
            graph: GraphData = repo.load_graph()
            if graph is None:
                return {"entities": [], "relations": []}
            return {
                "entities": [
                    {"id": e.id, "type": str(e.type), "properties": dict(e.properties)}
                    for e in (list(graph.entities.values()) if hasattr(graph.entities, "values") else graph.entities)
                ],
                "relations": [
                    {"source": r.subject, "relation_type": r.predicate, "target": r.object}
                    for r in (graph.relations if isinstance(graph.relations, list) else list(graph.relations))
                ],
            }
        except ImportError:
            raise ImportError("gw2radar not installed")

    def _handle_local_file(self, **params: Any) -> dict[str, Any]:
        path = Path(params.get("path", ""))
        if not path.exists():
            raise FileNotFoundError(f"file not found: {path}")
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw) if raw.strip().startswith(("{", "[")) else {"content": raw}
        if isinstance(data, list):
            data = {"items": data}
        return data

    def _handle_local_json(self, **params: Any) -> dict[str, Any]:
        data = params.get("data", {})
        if isinstance(data, str):
            data = json.loads(data)
        if isinstance(data, list):
            data = {"items": data}
        return data

    def _handle_static(self, **params: Any) -> dict[str, Any]:
        return {
            "items": params.get("items", []),
            "wallet": params.get("wallet", []),
            "characters": params.get("characters", []),
            "relations": params.get("relations", []),
        }

    @staticmethod
    def _count_records(data: Any) -> int:
        if isinstance(data, dict):
            count = 0
            for key in ("items", "wallet", "characters", "relations", "entities", "recipes", "achievements"):
                val = data.get(key, [])
                if isinstance(val, list):
                    count += len(val)
                elif isinstance(val, dict):
                    count += 1
            return count or (1 if data else 0)
        if isinstance(data, list):
            return len(data)
        return 1 if data else 0

    def clear_cache(self) -> int:
        count = len(self._cache)
        self._cache.clear()
        return count
