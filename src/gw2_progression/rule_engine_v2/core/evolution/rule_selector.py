from __future__ import annotations

import random
from typing import Any

from gw2_progression.rule_engine_v2.core.rl.reward_engine import RuleReward


class RuleSelector:
    def __init__(self, elite_ratio: float = 0.3, tournament_size: int = 3) -> None:
        self.elite_ratio = elite_ratio
        self.tournament_size = tournament_size
        self._rng = random.Random(1)

    def select_elite(self, rules: list[dict[str, Any]], reward: RuleReward | None = None) -> list[dict[str, Any]]:
        rw = reward or RuleReward()
        scored = [(r, rw.fitness(r)) for r in rules]
        scored.sort(key=lambda x: x[1], reverse=True)
        elite_count = max(1, int(len(rules) * self.elite_ratio))
        return [r for r, _ in scored[:elite_count]]

    def tournament_select(self, rules: list[dict[str, Any]], reward: RuleReward | None = None) -> dict[str, Any]:
        rw = reward or RuleReward()
        if len(rules) <= self.tournament_size:
            return max(rules, key=lambda r: rw.fitness(r))
        tournament = self._rng.sample(rules, min(self.tournament_size, len(rules)))
        return max(tournament, key=lambda r: rw.fitness(r))

    def select_by_diversity(self, rules: list[dict[str, Any]], k: int = 5) -> list[dict[str, Any]]:
        if len(rules) <= k:
            return rules
        selected: list[dict[str, Any]] = []
        for _ in range(k):
            remaining = [r for r in rules if r not in selected]
            if not remaining:
                break
            selected.append(self._rng.choice(remaining))
        return selected

    def rank_by_fitness(self, rules: list[dict[str, Any]], reward: RuleReward | None = None) -> list[tuple[dict[str, Any], float]]:
        rw = reward or RuleReward()
        scored = [(r, rw.fitness(r)) for r in rules]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored
