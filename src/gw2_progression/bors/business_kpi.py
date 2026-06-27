"""BusinessKPICalculator — normalizes runtime entity state into measurable KPIs (0..1).

KPI types map to DGSK entity types:
  - quality_score       ← qa_status / passed_checks
  - freshness_score     ← snapshot / build patch age
  - coverage_score      ← evidence / data source completeness
  - confidence_score    ← confidence metadata
  - reliability_score   ← action success rate
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class BusinessKPIType(Enum):
    QUALITY = "quality_score"
    FRESHNESS = "freshness_score"
    COVERAGE = "coverage_score"
    CONFIDENCE = "confidence_score"
    RELIABILITY = "reliability_score"
    LIQUIDITY = "liquidity_score"


@dataclass
class BusinessKPI:
    kpi_type: BusinessKPIType
    name: str
    value: float           # 0..1 normalized
    confidence: float = 1.0
    unit: str = "score"    # score / pct / bool
    trend: str = "stable"  # rising / falling / stable
    detail: str = ""


class BusinessKPICalculator:
    """Calculate normalized KPIs from ontology runtime state."""

    def calculate_all(self, **sources) -> list[BusinessKPI]:
        kpis: list[BusinessKPI] = []
        for kpi_type, method in [
            (BusinessKPIType.QUALITY, self._calc_quality),
            (BusinessKPIType.FRESHNESS, self._calc_freshness),
            (BusinessKPIType.COVERAGE, self._calc_coverage),
            (BusinessKPIType.CONFIDENCE, self._calc_confidence),
            (BusinessKPIType.RELIABILITY, self._calc_reliability),
            (BusinessKPIType.LIQUIDITY, self._calc_liquidity),
        ]:
            try:
                kpi = method(**sources)
                if kpi:
                    kpis.append(kpi)
            except Exception:
                pass
        return kpis

    # ── Individual KPI calculators ──

    def _calc_quality(self, **sources) -> BusinessKPI | None:
        """QA Gate results → quality_score."""
        qa = sources.get("qa_gate")
        if qa is None:
            return None
        if isinstance(qa, dict):
            passed = qa.get("passed", 0)
            total = qa.get("passed", 0) + qa.get("failed", 0)
            if total == 0:
                return None
            value = min(passed / max(total, 1), 1.0)
            return BusinessKPI(
                kpi_type=BusinessKPIType.QUALITY,
                name="Quality Score",
                value=value,
                unit="score",
                detail=f"{passed}/{total} checks passed",
            )
        return None

    def _calc_freshness(self, **sources) -> BusinessKPI | None:
        """Timestamps → freshness_score (1 = now, 0 = stale)."""
        snapshot_time = sources.get("snapshot_time", "")
        if not snapshot_time:
            return None
        try:
            ts = datetime.fromisoformat(snapshot_time.replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            age_hours = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
            value = max(0, 1 - age_hours / 48)  # 48h → 0
            return BusinessKPI(
                kpi_type=BusinessKPIType.FRESHNESS,
                name="Freshness Score",
                value=value,
                unit="score",
                detail=f"{age_hours:.1f}h old",
            )
        except (ValueError, TypeError):
            return None

    def _calc_coverage(self, **sources) -> BusinessKPI | None:
        """Data sources / evidence count → coverage_score."""
        data_sources = sources.get("data_sources", []) or []
        evidence_count = sources.get("evidence_count", 0)
        if not data_sources and not evidence_count:
            return None
        total = max(evidence_count + len(data_sources), 1)
        value = min(evidence_count / total, 1.0) if total > 0 else 0
        return BusinessKPI(
            kpi_type=BusinessKPIType.COVERAGE,
            name="Coverage Score",
            value=value,
            unit="score",
            detail=f"{evidence_count} evidence items from {len(data_sources)} sources",
        )

    def _calc_confidence(self, **sources) -> BusinessKPI | None:
        """Confidence metadata → normalized confidence_score."""
        confidence = sources.get("confidence", 0)
        if not isinstance(confidence, (int, float)):
            return None
        return BusinessKPI(
            kpi_type=BusinessKPIType.CONFIDENCE,
            name="Confidence Score",
            value=max(0, min(confidence, 1.0)),
            unit="score",
            detail=f"confidence={confidence}",
        )

    def _calc_reliability(self, **sources) -> BusinessKPI | None:
        """Action success rate → reliability_score."""
        action_history = sources.get("action_history", []) or []
        if not action_history:
            return None
        total = len(action_history)
        successes = sum(1 for a in action_history if isinstance(a, dict) and a.get("status") == "completed")
        if total == 0:
            return None
        return BusinessKPI(
            kpi_type=BusinessKPIType.RELIABILITY,
            name="Reliability Score",
            value=successes / total,
            unit="score",
            detail=f"{successes}/{total} actions succeeded",
        )

    def _calc_liquidity(self, **sources) -> BusinessKPI | None:
        """Price liquidity → liquidity_score (1=high, 0=illiquid)."""
        liquidity = sources.get("liquidity", "")
        mapping = {"high": 1.0, "medium": 0.6, "low": 0.3, "illiquid": 0.0, "unknown": 0.5}
        value = mapping.get(liquidity, 0.5)
        return BusinessKPI(
            kpi_type=BusinessKPIType.LIQUIDITY,
            name="Liquidity Score",
            value=value,
            unit="score",
            detail=f"liquidity={liquidity}",
        )
