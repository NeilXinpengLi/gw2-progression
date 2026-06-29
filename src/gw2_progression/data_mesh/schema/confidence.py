from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ConfidenceRecord:
    source_id: str
    source_type: str
    base_confidence: float
    adjusted_confidence: float
    adjustments: list[str] = field(default_factory=list)
    records_count: int = 0
    staleness_days: int = 0
    cross_validated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_type": self.source_type,
            "base_confidence": self.base_confidence,
            "adjusted_confidence": self.adjusted_confidence,
            "adjustments": self.adjustments,
            "records_count": self.records_count,
            "staleness_days": self.staleness_days,
            "cross_validated": self.cross_validated,
        }


class ConfidenceSystem:
    SOURCE_TYPE_BASE: dict[str, float] = {
        "official_api": 1.0,
        "official_wiki": 0.95,
        "official_forum": 0.90,
        "official_policy": 0.99,
        "public_build_site": 0.80,
        "competitor_tool": 0.70,
        "license_reference": 0.95,
        "community": 0.40,
    }

    CROSS_VALIDATION_BONUS: float = 0.05
    STALENESS_PENALTY_PER_DAY: float = 0.002
    MAX_STALENESS_PENALTY: float = 0.30

    def __init__(self, source_registry: Any | None = None):
        from gw2_progression.data_mesh.sources.registry import SourceRegistry
        self._registry: SourceRegistry = source_registry or SourceRegistry()

    def evaluate(
        self,
        source_type: str,
        source_id: str | None = None,
        records_count: int = 1,
        staleness_days: int = 0,
        cross_validation_count: int = 0,
    ) -> ConfidenceRecord:
        base = self.SOURCE_TYPE_BASE.get(source_type, 0.5)

        adjustments: list[str] = []
        adjusted = base

        if source_id and self._registry.get(source_id):
            source = self._registry.get(source_id)
            adjusted = (adjusted + source.default_confidence) / 2
            adjustments.append(f"registry override: {source.default_confidence}")

        if records_count <= 0:
            adjustments.append("zero records")
            adjusted *= 0.5
        elif records_count == 1:
            adjustments.append("single record")
            adjusted *= 0.9

        if staleness_days > 0:
            penalty = min(
                staleness_days * self.STALENESS_PENALTY_PER_DAY,
                self.MAX_STALENESS_PENALTY,
            )
            if penalty > 0:
                adjustments.append(f"staleness penalty: -{penalty:.3f}")
                adjusted -= penalty

        cross_validated = cross_validation_count > 0
        if cross_validated:
            bonus = self.CROSS_VALIDATION_BONUS * min(cross_validation_count, 5)
            adjustments.append(f"cross-validated: +{bonus:.3f} ({cross_validation_count} sources)")
            adjusted += bonus

        adjusted = max(0.0, min(1.0, adjusted))

        return ConfidenceRecord(
            source_id=source_id or f"anonymous:{source_type}",
            source_type=source_type,
            base_confidence=base,
            adjusted_confidence=round(adjusted, 4),
            adjustments=adjustments,
            records_count=records_count,
            staleness_days=staleness_days,
            cross_validated=cross_validated,
        )

    def adjust_for_merge(self, records: list[ConfidenceRecord]) -> float:
        if not records:
            return 0.0
        weighted = sum(r.adjusted_confidence * max(r.records_count, 1) for r in records)
        total_weight = sum(max(r.records_count, 1) for r in records)
        return round(weighted / total_weight, 4)
