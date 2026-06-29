from __future__ import annotations

from typing import Any

from gw2_progression.lifecycle.core.backward.inference_engine import InferredPath


class PathRanker:
    def __init__(self, weights: dict[str, float] | None = None) -> None:
        self.weights = weights or {
            "probability": 1.0,
            "rule_consistency": 1.0,
            "economy_likelihood": 1.0,
            "step_diversity": 0.5,
            "length_penalty": 0.3,
        }

    def rank(self, paths: list[InferredPath]) -> list[InferredPath]:
        scored = [(p, self._score(p)) for p in paths]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [p for p, _ in scored]

    def rank_with_metadata(self, paths: list[InferredPath]) -> list[dict[str, Any]]:
        scored = [(p, self._score(p)) for p in paths]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [
            {
                "path": p,
                "score": round(score, 4),
                "probability": p.probability,
                "rule_consistency": p.rule_consistency,
                "economy_likelihood": p.economy_likelihood,
                "step_count": len(p.steps),
                "step_types": list(set(s.get("type", "") for s in p.steps)),
            }
            for p, score in scored
        ]

    def _score(self, path: InferredPath) -> float:
        if not path.steps:
            return 0.0
        w = self.weights
        prob_score = path.probability * w["probability"]
        consistency_score = path.rule_consistency * w["rule_consistency"]
        economy_score = path.economy_likelihood * w["economy_likelihood"]
        step_types = set(s.get("type", "") for s in path.steps)
        diversity = min(len(step_types) / 5, 1.0) * w["step_diversity"]
        length_penalty = max(0, 1.0 - (len(path.steps) / 20) * w["length_penalty"])
        total_weight = w["probability"] + w["rule_consistency"] + w["economy_likelihood"] + w["step_diversity"] + w["length_penalty"]
        return (prob_score + consistency_score + economy_score + diversity + length_penalty) / total_weight

    def get_top_k(self, paths: list[InferredPath], k: int = 3) -> list[InferredPath]:
        ranked = self.rank(paths)
        return ranked[:k]

    def get_alternatives(self, paths: list[InferredPath], top_n: int = 3) -> list[InferredPath]:
        ranked = self.rank(paths)
        if len(ranked) <= top_n:
            return ranked[1:]
        return ranked[1:top_n + 1]
