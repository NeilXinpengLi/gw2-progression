from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class RuleNode:
    id: str
    node_type: str
    features: np.ndarray
    label: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.features, list):
            self.features = np.array(self.features, dtype=np.float32)


@dataclass
class RuleEdge:
    source: str
    target: str
    edge_type: str
    weight: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RuleGraph:
    nodes: dict[str, RuleNode] = field(default_factory=dict)
    edges: list[RuleEdge] = field(default_factory=list)

    @property
    def adjacency(self) -> np.ndarray:
        n = len(self.nodes)
        node_ids = list(self.nodes.keys())
        id_map = {nid: i for i, nid in enumerate(node_ids)}
        adj = np.zeros((n, n), dtype=np.float32)
        for edge in self.edges:
            if edge.source in id_map and edge.target in id_map:
                adj[id_map[edge.source], id_map[edge.target]] = edge.weight
                adj[id_map[edge.target], id_map[edge.source]] = edge.weight
        return adj

    @property
    def feature_matrix(self) -> np.ndarray:
        if not self.nodes:
            return np.zeros((0, 4), dtype=np.float32)
        return np.array([n.features for n in self.nodes.values()], dtype=np.float32)


class RuleEncoder:
    def __init__(self, embedding_dim: int = 8) -> None:
        self.embedding_dim = embedding_dim
        self._rng = random.Random(1)

    def encode_rule(self, rule: dict[str, Any]) -> RuleNode:
        rule_type = rule.get("type", "unknown")
        feature_map = {
            "crafting": [1, 0, 0, 0, rule.get("complexity", 0.5), rule.get("profit", 0), rule.get("rarity", 0.5), 0],
            "economy": [0, 1, 0, 0, rule.get("volatility", 0.5), rule.get("spread", 0), rule.get("liquidity", 0.5), 0],
            "behavior": [0, 0, 1, 0, rule.get("frequency", 0.5), rule.get("adaptability", 0), rule.get("consistency", 0.5), 0],
            "meta": [0, 0, 0, 1, rule.get("generality", 0.5), rule.get("transferability", 0), rule.get("robustness", 0.5), 0],
        }
        base = feature_map.get(rule_type, [0, 0, 0, 0, 0.5, 0, 0.5, 0])
        features = np.array(base[:self.embedding_dim], dtype=np.float32)
        if len(features) < self.embedding_dim:
            features = np.pad(features, (0, self.embedding_dim - len(features)))
        return RuleNode(
            id=rule.get("id", f"rule:{self._rng.randint(1000, 9999)}"),
            node_type=rule_type,
            features=features,
            label=rule.get("name", rule_type),
            metadata=rule,
        )

    def encode_rules(self, rules: list[dict[str, Any]]) -> list[RuleNode]:
        return [self.encode_rule(r) for r in rules]

    def build_graph(self, nodes: list[RuleNode], edges: list[RuleEdge] | None = None) -> RuleGraph:
        graph = RuleGraph()
        for node in nodes:
            graph.nodes[node.id] = node
        if edges:
            graph.edges.extend(edges)
        else:
            for i in range(len(nodes)):
                for j in range(i + 1, len(nodes)):
                    sim = self._similarity(nodes[i].features, nodes[j].features)
                    if sim > 0.3:
                        graph.edges.append(RuleEdge(
                            source=nodes[i].id,
                            target=nodes[j].id,
                            edge_type="similar",
                            weight=round(sim, 4),
                        ))
        return graph

    def _similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))
