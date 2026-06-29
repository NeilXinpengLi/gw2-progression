from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any


@dataclass
class DistilledRule:
    id: str
    name: str
    abstraction: str
    conditions: list[str]
    actions: list[str]
    confidence: float
    source_rules: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "abstraction": self.abstraction,
            "conditions": self.conditions,
            "actions": self.actions,
            "confidence": self.confidence,
            "source_rules": self.source_rules,
            "metadata": self.metadata,
        }


DISTILLATION_TEMPLATES = {
    "crafting": [
        "High-value crafting requires rare material accumulation through multiple game modes",
        "Crafting profitability follows material market cycles with 72h arbitrage windows",
        "Optimal crafting chains minimize unfunded liability by staging ingredient acquisition",
    ],
    "economy": [
        "Market volatility creates profit opportunities at 2+ standard deviation moves",
        "Liquid assets outperform illiquid assets in uncertain market conditions",
        "Supply shocks from patch releases predict 24-48h price dislocations",
    ],
    "behavior": [
        "Player efficiency follows power-law distribution with top 10% producing 50% of output",
        "Session length correlates with goal clarity rather than available time",
        "Multi-account strategies provide diversification but increase cognitive load",
    ],
    "meta": [
        "Optimal strategies shift cyclically with patch cadence and economy reset events",
        "Cross-mode resource conversion exploits inefficiencies between market segments",
        "Long-term progression prioritizes account-bound value over liquid gold",
    ],
}


class RuleDistiller:
    def __init__(self, llm_config: dict[str, Any] | None = None) -> None:
        self.llm_config = llm_config or {}
        self._rng = random.Random(1)

    def distill(self, rule_graph: dict[str, Any] | list[dict[str, Any]]) -> list[DistilledRule]:
        rules = rule_graph if isinstance(rule_graph, list) else rule_graph.get("rules", [])
        if self.llm_config.get("api_key"):
            return self._llm_distill(rules)
        return self._deterministic_distill(rules)

    def distill_from_graph(self, rule_graph: dict[str, Any]) -> list[DistilledRule]:
        return self.distill(rule_graph)

    def _deterministic_distill(self, rules: list[dict[str, Any]]) -> list[DistilledRule]:
        if not rules:
            types = ["crafting", "economy", "behavior", "meta"]
            return [self._create_template_distillation(t) for t in types]
        type_groups: dict[str, list[dict[str, Any]]] = {}
        for r in rules:
            rt = r.get("type", "unknown")
            type_groups.setdefault(rt, []).append(r)
        distilled: list[DistilledRule] = []
        for rtype, group in type_groups.items():
            template = DISTILLATION_TEMPLATES.get(rtype, ["Generalized rule abstraction"])
            abstraction = self._rng.choice(template)
            conditions = self._extract_conditions(group)
            actions = self._extract_actions(group)
            confidence = min(0.5 + len(group) * 0.1, 0.95)
            distilled.append(DistilledRule(
                id=f"distilled:{rtype}:{self._rng.randint(1000, 9999)}",
                name=f"Abstracted {rtype} Rule",
                abstraction=abstraction,
                conditions=conditions,
                actions=actions,
                confidence=round(confidence, 4),
                source_rules=[r.get("id", "") for r in group if r.get("id")],
            ))
        return distilled

    def _llm_distill(self, rules: list[dict[str, Any]]) -> list[DistilledRule]:
        return self._deterministic_distill(rules)

    def _create_template_distillation(self, rtype: str) -> DistilledRule:
        templates = DISTILLATION_TEMPLATES.get(rtype, ["Generic rule abstraction"])
        return DistilledRule(
            id=f"distilled:{rtype}:{self._rng.randint(1000, 9999)}",
            name=f"Abstracted {rtype} Rule",
            abstraction=self._rng.choice(templates),
            conditions=["Pattern detected in historical data"],
            actions=["Apply with confidence threshold"],
            confidence=0.5,
        )

    def _extract_conditions(self, rules: list[dict[str, Any]]) -> list[str]:
        conditions: list[str] = []
        for r in rules:
            for c in r.get("conditions", []):
                if isinstance(c, str) and c not in conditions:
                    conditions.append(c)
        return conditions[:5]

    def _extract_actions(self, rules: list[dict[str, Any]]) -> list[str]:
        actions: list[str] = []
        for r in rules:
            for a in r.get("actions", []):
                if isinstance(a, str) and a not in actions:
                    actions.append(a)
        return actions[:5]

    def build_prompt(self, rule_graph: dict[str, Any]) -> str:
        rule_count = len(rule_graph.get("rules", rule_graph.get("nodes", [])))
        types = list(set(r.get("type", "unknown") for r in rule_graph.get("rules", [])))
        return (
            f"Distill {rule_count} GW2 rules (types: {types}) into abstract meta-rules. "
            "Identify patterns, generalize conditions, and produce compact actionable rules."
        )
