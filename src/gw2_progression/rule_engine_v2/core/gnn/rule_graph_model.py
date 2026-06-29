from __future__ import annotations

from typing import Any

import numpy as np

from gw2_progression.rule_engine_v2.core.gnn.message_passing import MessagePassingNetwork
from gw2_progression.rule_engine_v2.core.gnn.rule_encoder import RuleEdge, RuleEncoder, RuleGraph


class RuleGNN:
    def __init__(self, input_dim: int = 8, hidden_dim: int = 16, output_dim: int = 8, num_layers: int = 3) -> None:
        self.encoder = RuleEncoder(embedding_dim=input_dim)
        self.mpnn = MessagePassingNetwork(
            input_dim=input_dim,
            hidden_dim=hidden_dim,
            output_dim=output_dim,
            num_layers=num_layers,
        )
        self.graph: RuleGraph | None = None

    def encode(self, rules: list[dict[str, Any]], edges: list[RuleEdge] | None = None) -> RuleGraph:
        nodes = self.encoder.encode_rules(rules)
        self.graph = self.encoder.build_graph(nodes, edges)
        return self.graph

    def forward(self, rule_graph: RuleGraph | None = None) -> np.ndarray:
        g = rule_graph or self.graph
        if g is None or not g.nodes:
            return np.zeros((0, self.mpnn.layers[-1].output_dim), dtype=np.float32)
        features = g.feature_matrix
        adjacency = g.adjacency
        return self.mpnn.forward(features, adjacency)

    def forward_with_rules(self, rules: list[dict[str, Any]]) -> np.ndarray:
        self.encode(rules)
        return self.forward()

    def get_embeddings(self, rules: list[dict[str, Any]]) -> dict[str, list[float]]:
        embeddings = self.forward_with_rules(rules)
        if self.graph is None:
            return {}
        node_ids = list(self.graph.nodes.keys())
        return {
            nid: embeddings[i].tolist() if i < len(embeddings) else []
            for i, nid in enumerate(node_ids)
        }

    def predict_rule_quality(self, rule_embedding: np.ndarray) -> float:
        quality = float(np.mean(np.abs(rule_embedding)))
        return float(1.0 / (1.0 + np.exp(-quality)))

    def compute_rule_similarity(self, emb_a: np.ndarray, emb_b: np.ndarray) -> float:
        norm_a = np.linalg.norm(emb_a)
        norm_b = np.linalg.norm(emb_b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(emb_a, emb_b) / (norm_a * norm_b))

    def discover_rule_clusters(self, rules: list[dict[str, Any]], n_clusters: int = 3) -> dict[int, list[str]]:
        embeddings = self.forward_with_rules(rules)
        if len(embeddings) == 0 or self.graph is None:
            return {}
        node_ids = list(self.graph.nodes.keys())
        centroids = embeddings[np.random.choice(len(embeddings), min(n_clusters, len(embeddings)), replace=False)]
        clusters: dict[int, list[str]] = {i: [] for i in range(len(centroids))}
        for i, nid in enumerate(node_ids):
            if i < len(embeddings):
                distances = np.linalg.norm(centroids - embeddings[i], axis=1)
                cluster_id = int(np.argmin(distances))
                clusters[cluster_id].append(nid)
        return clusters
