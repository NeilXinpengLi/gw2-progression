"""Rule consistency checker — validates rule coherence, detects conflicts, and deduplicates."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from gw2_progression.rule_engine.core.api_rules.schema_parser import Rule


class RuleChecker:
    """Checks rule consistency, detects conflicts, and deduplicates."""

    def check(self, rules: list[Rule]) -> dict[str, Any]:
        return {
            "total": len(rules),
            "conflicts": self._detect_conflicts(rules),
            "duplicates": self._detect_duplicates(rules),
            "by_type": dict(self._count_by_type(rules)),
            "avg_confidence": round(sum(r.confidence for r in rules) / max(len(rules), 1), 3),
        }

    def _detect_conflicts(self, rules: list[Rule]) -> list[dict[str, Any]]:
        conflicts: list[dict[str, Any]] = []
        grouped = defaultdict(list)
        for r in rules:
            key = (r.source, r.action)
            grouped[key].append(r)
        for key, group in grouped.items():
            if len(group) > 1 and len({r.type.value for r in group}) > 1:
                conflicts.append({
                    "source": key[0],
                    "action": key[1],
                    "rule_ids": [r.id for r in group],
                    "types": [r.type.value for r in group],
                })
        return conflicts

    def _detect_duplicates(self, rules: list[Rule]) -> list[dict[str, Any]]:
        seen: dict[str, list[Rule]] = defaultdict(list)
        for r in rules:
            key = f"{r.source}|{r.action}|{r.condition}"
            seen[key].append(r)
        return [
            {"key": k, "count": len(v), "rule_ids": [r.id for r in v]}
            for k, v in seen.items() if len(v) > 1
        ]

    def _count_by_type(self, rules: list[Rule]) -> dict[str, int]:
        counts: dict[str, int] = defaultdict(int)
        for r in rules:
            counts[r.type.value] += 1
        return dict(counts)
