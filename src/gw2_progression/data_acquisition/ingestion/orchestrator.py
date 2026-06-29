from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable

from gw2_progression.data_acquisition.contract import DataExpansionRecord
from gw2_progression.data_acquisition.coverage import ActiveRefreshPlanner, CoverageAnalyzer
from gw2_progression.data_acquisition.ingestion.fetcher import Fetcher
from gw2_progression.data_acquisition.ingestion.normalizer import Normalizer
from gw2_progression.data_acquisition.persistence import DataExpansionStore
from gw2_progression.data_acquisition.registry.source_registry import SourceConfig, SourceRegistry


@dataclass
class IngestionEvent:
    source_id: str
    source_type: str
    status: str
    entities_count: int
    relations_count: int
    duration_ms: float
    error: str | None = None
    timestamp: float = 0.0


@dataclass
class IngestionResult:
    source_id: str
    success: bool
    events: list[IngestionEvent]
    total_entities: int = 0
    total_relations: int = 0
    duration_ms: float = 0.0
    records_written: int = 0
    coverage: dict[str, Any] = field(default_factory=dict)
    refresh_requests: list[dict[str, Any]] = field(default_factory=list)


class IngestionOrchestrator:
    """Multi-source ingestion orchestrator.

    Manages the full pipeline for each source:
      Source → Fetch → Normalize → Expand → Graph → Store

    Supports calling an external expansion engine and graph builder.
    """

    def __init__(
        self,
        registry: SourceRegistry | None = None,
        fetcher: Fetcher | None = None,
        normalizer: Normalizer | None = None,
        store: DataExpansionStore | None = None,
    ) -> None:
        self.registry = registry or SourceRegistry()
        self.fetcher = fetcher or Fetcher()
        self.normalizer = normalizer or Normalizer()
        self.store = store or DataExpansionStore()
        self.coverage_analyzer = CoverageAnalyzer(self.registry)
        self.refresh_planner = ActiveRefreshPlanner(self.registry)

        self._expansion_hooks: list[Callable[[dict[str, Any], SourceConfig], dict[str, Any]]] = []
        self._graph_hooks: list[Callable[[dict[str, Any]], None]] = []
        self._event_history: list[IngestionEvent] = []

    def register_expansion_hook(self, hook: Callable[[dict[str, Any], SourceConfig], dict[str, Any]]) -> None:
        self._expansion_hooks.append(hook)

    def register_graph_hook(self, hook: Callable[[dict[str, Any]], None]) -> None:
        self._graph_hooks.append(hook)

    def ingest_source(self, source: SourceConfig) -> IngestionResult:
        """Ingest a single source through the full pipeline."""
        start = time.time()
        events: list[IngestionEvent] = []

        try:
            raw = self.fetcher.fetch(source)
            events.append(IngestionEvent(
                source_id=source.id, source_type=source.type.value,
                status="fetched", entities_count=0, relations_count=0,
                duration_ms=(time.time() - start) * 1000,
            ))

            normalized = self.normalizer.normalize(raw, source)
            entities = normalized.get("entities", [])
            relations = normalized.get("relations", [])
            events.append(IngestionEvent(
                source_id=source.id, source_type=source.type.value,
                status="normalized", entities_count=len(entities),
                relations_count=len(relations),
                duration_ms=(time.time() - start) * 1000,
            ))

            expanded = self._run_expansion(normalized, source)

            self._run_graph_hooks(expanded)
            records = self._records_from_expanded(expanded, source, collected_at=time.time())
            persist_result = self.store.write_records(records)
            coverage = self.coverage_analyzer.analyze(self.store.list_records()).to_dict()
            refresh_requests = [r.to_dict() for r in self.refresh_planner.plan(self.coverage_analyzer.analyze(self.store.list_records()))]

            duration = (time.time() - start) * 1000
            self._event_history.extend(events)
            return IngestionResult(
                source_id=source.id,
                success=True,
                events=events,
                total_entities=len(entities),
                total_relations=len(relations),
                duration_ms=round(duration, 2),
                records_written=int(persist_result.get("written", 0)),
                coverage=coverage,
                refresh_requests=refresh_requests,
            )

        except Exception as e:
            error_event = IngestionEvent(
                source_id=source.id, source_type=source.type.value,
                status="failed", entities_count=0, relations_count=0,
                duration_ms=(time.time() - start) * 1000,
                error=str(e), timestamp=time.time(),
            )
            self._event_history.append(error_event)
            return IngestionResult(
                source_id=source.id, success=False,
                events=[error_event], duration_ms=round((time.time() - start) * 1000, 2),
            )

    def ingest_all(self) -> list[IngestionResult]:
        """Ingest all enabled sources."""
        results: list[IngestionResult] = []
        for source in self.registry.get_sorted():
            results.append(self.ingest_source(source))
        return results

    def ingest_by_type(self, source_type: str) -> list[IngestionResult]:
        """Ingest all sources of a specific type."""
        results: list[IngestionResult] = []
        for source in self.registry.get_enabled():
            if source.type.value == source_type:
                results.append(self.ingest_source(source))
        return results

    def _run_expansion(self, data: dict[str, Any], source: SourceConfig) -> dict[str, Any]:
        result = dict(data)
        for hook in self._expansion_hooks:
            try:
                result = hook(result, source)
            except Exception:
                pass
        return result

    def _run_graph_hooks(self, data: dict[str, Any]) -> None:
        for hook in self._graph_hooks:
            try:
                hook(data)
            except Exception:
                pass

    def _records_from_expanded(self, data: dict[str, Any], source: SourceConfig, collected_at: float) -> list[DataExpansionRecord]:
        observed_at = float(data.get("observed_at") or collected_at)
        return [
            DataExpansionRecord.from_entity(
                entity,
                source_id=source.id,
                source_type=source.type.value,
                collected_at=collected_at,
                observed_at=float(entity.get("timestamp") or observed_at),
                confidence=source.confidence_default,
                privacy_scope=source.privacy_scope,
            )
            for entity in data.get("entities", [])
        ]

    @property
    def total_ingested(self) -> int:
        return sum(1 for e in self._event_history if e.status == "normalized")

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_sources": len(self.registry.get_enabled()),
            "total_ingested": self.total_ingested,
            "total_events": len(self._event_history),
            "stored_records": self.store.count(),
            "coverage": self.coverage_analyzer.analyze(self.store.list_records()).to_dict(),
            "active_refresh": [r.to_dict() for r in self.refresh_planner.plan(self.coverage_analyzer.analyze(self.store.list_records()))[:10]],
            "recent_events": [
                {
                    "source_id": e.source_id,
                    "status": e.status,
                    "entities": e.entities_count,
                    "relations": e.relations_count,
                    "duration_ms": round(e.duration_ms, 1),
                    "error": e.error,
                }
                for e in self._event_history[-10:]
            ],
            "registry": self.registry.to_dict(),
        }
