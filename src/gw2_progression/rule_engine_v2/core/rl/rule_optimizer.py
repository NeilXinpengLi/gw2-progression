from __future__ import annotations

import copy
import random
from typing import Any

from gw2_progression.rule_engine_v2.core.rl.reward_engine import RuleReward
from gw2_progression.rule_engine_v2.core.rl.rule_policy import RulePolicy


class RuleOptimizer:
    def __init__(self, policy: RulePolicy | None = None, reward: RuleReward | None = None, learning_rate: float = 0.01) -> None:
        self.policy = policy or RulePolicy(learning_rate=learning_rate)
        self.reward = reward or RuleReward()
        self.lr = learning_rate
        self._rng = random.Random(1)
        self.optimization_history: list[dict[str, Any]] = []

    def reward(self, rule: dict[str, Any]) -> float:
        return self.reward.fitness(rule)

    def update(self, rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
        optimized: list[dict[str, Any]] = []
        for rule in rules:
            action = self.policy.select_action(rule)
            modified = self._apply_action(rule, action)
            rew = self.reward.fitness(modified)
            self.policy.update(rule.get("id", "unknown"), action, rew)
            optimized.append(modified)
            self.optimization_history.append({
                "rule_id": rule.get("id"),
                "action": action,
                "reward": rew,
            })
        return optimized

    def _apply_action(self, rule: dict[str, Any], action: str) -> dict[str, Any]:
        r = copy.deepcopy(rule)
        if action == "apply":
            r["active"] = True
        elif action == "skip":
            r["active"] = False
        elif action == "modify":
            r["base_accuracy"] = min((r.get("base_accuracy", 0.7) + self._rng.uniform(-0.1, 0.1)), 1.0)
            r["profit"] = max(0, r.get("profit", 0) + self._rng.uniform(-5, 5))
        elif action == "defer":
            r["priority"] = max(0, r.get("priority", 1) - 1)
        elif action == "merge":
            r["merged"] = True
            r["base_accuracy"] = min(r.get("base_accuracy", 0.7) * 1.05, 1.0)
        return r

    def gradient_update(self, rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return self.update(rules)

    def get_best_rules(self, rules: list[dict[str, Any]], k: int = 5) -> list[dict[str, Any]]:
        scored = [(r, self.reward.fitness(r)) for r in rules]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [r for r, _ in scored[:k]]
