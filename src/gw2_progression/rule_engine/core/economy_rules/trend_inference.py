"""Trend inference — high-level economic pattern detection from multiple item series.

Identifies market-wide patterns: patch-driven inflation, seasonal cycles, liquidity crises.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any


class TrendInference:
    """Infers market-wide economic trends from aggregate price data."""

    def infer(self, all_rules: list[dict[str, Any]]) -> dict[str, Any]:
        trends: dict[str, Any] = {}

        by_direction = defaultdict(int)
        for r in all_rules:
            cond = r.get("condition", {})
            if r.get("type") == "economy_trend" and "direction" in cond:
                by_direction[cond["direction"]] += 1
        total = max(sum(by_direction.values()), 1)
        trends["market_bias"] = {k: round(v / total, 3) for k, v in by_direction.items()}

        elasticities = [r.get("condition", {}).get("elasticity", 0) for r in all_rules if "elasticity" in r.get("condition", {})]
        trends["avg_elasticity"] = round(sum(elasticities) / max(len(elasticities), 1), 3) if elasticities else 0

        shock_count = len([r for r in all_rules if r.get("type") == "economy_shock"])
        trends["shock_frequency"] = shock_count

        return trends
