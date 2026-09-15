"""Builds a dependency/relation graph from extracted API rules.

Converts the flat list of API rules into a traversable graph structure
that can be used by OOSK for runtime reasoning.
"""

from __future__ import annotations

from typing import Any

from gw2_progression.rule_engine.core.api_rules.schema_parser import Rule


class RuleGraph:
    """Graph of rules with dependency resolution and traversal."""

    def __init__(self) -> None:
        self.nodes: dict[str, dict[str, Any]] = {}
        self.edges: list[dict[str, Any]] = []

    def add_rule(self, rule: Rule) -> None:
        node_id = rule.source
        self.nodes.setdefault(node_id, {"id": node_id, "rules": [], "types": set()})
        self.nodes[node_id]["rules"].append(rule.to_dict())
        self.nodes[node_id]["types"].add(rule.type.value)

    def add_edge(self, source_id: str, target_id: str, relation: str, confidence: float = 1.0) -> None:
        self.edges.append({"source": source_id, "target": target_id, "relation": relation, "confidence": confidence})


class RuleGraphBuilder:
    """Builds a RuleGraph from extracted API rules."""

    def build(self, rules: list[Rule]) -> RuleGraph:
        graph = RuleGraph()
        for rule in rules:
            graph.add_rule(rule)
        return graph
