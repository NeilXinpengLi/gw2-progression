from __future__ import annotations

import time
from collections import Counter

from gw2_progression.data_acquisition.contract import ActiveRefreshRequest, DataCoverageReport, DataExpansionRecord
from gw2_progression.data_acquisition.registry.source_registry import SourceRegistry

REQUIRED_ENTITY_TYPES = {
    "item",
    "market_item",
    "recipe",
    "synthetic_entity",
    "dependency_tree",
    "merged_asset",
    "craft_profit_opportunity",
}


class CoverageAnalyzer:
    """Computes data expansion coverage and gaps from durable records."""

    def __init__(self, registry: SourceRegistry | None = None, required_entity_types: set[str] | None = None) -> None:
        self.registry = registry or SourceRegistry()
        self.required_entity_types = required_entity_types or REQUIRED_ENTITY_TYPES

    def analyze(self, records: list[DataExpansionRecord], now: float | None = None) -> DataCoverageReport:
        now = time.time() if now is None else now
        sources = Counter(r.source_id for r in records)
        entity_types = Counter(r.entity_type for r in records)
        privacy_scopes = Counter(r.privacy_scope for r in records)
        buckets = Counter(self._confidence_bucket(r.confidence) for r in records)
        latest_by_source: dict[str, float] = {}
        for record in records:
            latest_by_source[record.source_id] = max(latest_by_source.get(record.source_id, 0.0), record.observed_at)

        stale_sources = []
        for source in self.registry.get_enabled():
            latest = latest_by_source.get(source.id, 0.0)
            if latest == 0.0 or now - latest > source.freshness_sla_seconds:
                stale_sources.append(source.id)

        missing = sorted(self.required_entity_types.difference(entity_types.keys()))
        return DataCoverageReport(
            total_records=len(records),
            sources=dict(sources),
            entity_types=dict(entity_types),
            privacy_scopes=dict(privacy_scopes),
            confidence_buckets=dict(buckets),
            stale_sources=stale_sources,
            missing_entity_types=missing,
            generated_at=now,
        )

    def _confidence_bucket(self, confidence: float) -> str:
        if confidence >= 0.85:
            return "high"
        if confidence >= 0.6:
            return "medium"
        return "low"


class ActiveRefreshPlanner:
    """Turns coverage gaps into prioritized source refresh requests."""

    def __init__(self, registry: SourceRegistry | None = None) -> None:
        self.registry = registry or SourceRegistry()

    def plan(self, report: DataCoverageReport) -> list[ActiveRefreshRequest]:
        requests: list[ActiveRefreshRequest] = []
        for source_id in report.stale_sources:
            source = self.registry.get(source_id)
            priority = int(source.priority.value if source else 3)
            requests.append(ActiveRefreshRequest(source_id=source_id, reason="stale_source", priority=priority))

        for entity_type in report.missing_entity_types:
            for source in self._candidate_sources(entity_type):
                requests.append(ActiveRefreshRequest(source_id=source.id, reason="missing_entity_type", priority=int(source.priority.value), entity_type=entity_type))

        return sorted(requests, key=lambda r: (r.priority, r.source_id, r.entity_type or ""))

    def _candidate_sources(self, entity_type: str):
        if entity_type == "market_item":
            return [s for s in self.registry.get_enabled() if s.type.value in {"api", "market", "tool"} and ("tp" in s.id or "price" in s.id or s.type.value == "market")]
        if entity_type in {"recipe", "dependency_tree", "craft_profit_opportunity"}:
            return [s for s in self.registry.get_enabled() if s.type.value in {"wiki", "api"}]
        if entity_type == "synthetic_entity":
            return [s for s in self.registry.get_enabled() if s.type.value == "synthetic"]
        return self.registry.get_enabled()[:1]
