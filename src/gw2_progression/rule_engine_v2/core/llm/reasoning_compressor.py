from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any


@dataclass
class CompressedReasoning:
    id: str
    original_length: int
    compressed_length: int
    compression_ratio: float
    summary: str
    key_insights: list[str]
    confidence: float


class ReasoningCompressor:
    def __init__(self) -> None:
        self._rng = random.Random(1)

    def compress(self, reasoning_chain: list[dict[str, Any]], max_steps: int = 5) -> CompressedReasoning:
        original_length = len(reasoning_chain)
        if original_length <= max_steps:
            steps = reasoning_chain
            ratio = 1.0
        else:
            step = original_length // max_steps
            steps = [reasoning_chain[i] for i in range(0, original_length, step)][:max_steps]
            ratio = max_steps / max(original_length, 1)
        summary = self._build_summary(steps)
        insights = self._extract_insights(steps)
        return CompressedReasoning(
            id=f"compressed:{self._rng.randint(10000, 99999)}",
            original_length=original_length,
            compressed_length=len(steps),
            compression_ratio=round(ratio, 4),
            summary=summary,
            key_insights=insights,
            confidence=round(0.7 + ratio * 0.2, 4),
        )

    def compress_batch(self, chains: list[list[dict[str, Any]]]) -> list[CompressedReasoning]:
        return [self.compress(c) for c in chains]

    def _build_summary(self, steps: list[dict[str, Any]]) -> str:
        if not steps:
            return "Empty reasoning chain"
        types = list(set(s.get("type", "step") for s in steps))
        items = list(set(s.get("item_id", "") for s in steps if s.get("item_id")))
        summary = f"Reasoning through {len(steps)} steps"
        if types:
            summary += f" involving {', '.join(types[:3])}"
        if items:
            summary += f" for {', '.join(items[:3])}"
        return summary

    def _extract_insights(self, steps: list[dict[str, Any]]) -> list[str]:
        insights: list[str] = []
        for s in steps:
            if s.get("type") == "trade":
                insights.append("Trade opportunity at step with price impact")
            elif s.get("type") == "craft":
                insights.append("Crafting unlocks value-add transformation")
            elif s.get("type") == "achievement":
                insights.append("Achievement progression unlocks account power")
        return list(set(insights))[:3]

    def compress_reasoning_graph(self, graph: dict[str, Any]) -> dict[str, Any]:
        chains = graph.get("reasoning_chains", [])
        compressed = self.compress_batch(chains)
        return {
            "original_chains": len(chains),
            "compressed": [c.__dict__ for c in compressed],
            "avg_compression": round(sum(c.compression_ratio for c in compressed) / max(len(compressed), 1), 4),
        }
