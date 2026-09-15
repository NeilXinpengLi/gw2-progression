"""Reasoning chain to rule converter — transforms Expert AI reasoning chains into structured rules.

Bridges the existing ReasoningEngine output into the Rule Engine's rule format.
"""

from __future__ import annotations

from typing import Any

from gw2_progression.rule_engine.core.api_rules.schema_parser import Rule, RuleType


class ReasoningConverter:
    """Converts reasoning chains from the Expert AI ReasoningEngine into structured rules."""

    def convert(self, reasoning: dict[str, Any] | list[dict[str, Any]]) -> list[Rule]:
        rules: list[Rule] = []
        chain = reasoning.get("reasoning_chain", reasoning) if isinstance(reasoning, dict) else reasoning
        if isinstance(chain, list):
            for step in chain:
                rules.append(self._step_to_rule(step))
        return rules

    def _step_to_rule(self, step: dict[str, Any]) -> Rule:
        node = step.get("node", step.get("from", "unknown"))
        target = step.get("target", step.get("to", "unknown"))
        relation = step.get("relation", "related_to")
        claim = step.get("claim", f"{node} -> {target}")
        return Rule(
            id=f"reason_{node}_{relation}_{target}",
            type=RuleType.GRAPH_EDGE,
            source=f"reasoning:{node}",
            condition={"node": node, "relation": relation, "target": target, "claim": claim},
            action=f"infer_{relation}",
            confidence=step.get("confidence", 0.7),
            metadata={"chain_step": step, "reasoning_type": "trace"},
        )

    def convert_batch(self, reasoning_list: list[dict[str, Any]]) -> list[Rule]:
        all_rules: list[Rule] = []
        for r in reasoning_list:
            all_rules.extend(self.convert(r))
        return all_rules
