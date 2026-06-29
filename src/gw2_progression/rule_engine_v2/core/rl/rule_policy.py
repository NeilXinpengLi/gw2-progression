from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any


@dataclass
class RulePolicyState:
    rule_id: str
    features: list[float]
    action_space: list[str]
    selected_action: str = ""
    reward: float = 0.0


class RulePolicy:
    def __init__(self, learning_rate: float = 0.01, exploration_rate: float = 0.2) -> None:
        self.lr = learning_rate
        self.epsilon = exploration_rate
        self._rng = random.Random(1)
        self.q_table: dict[str, dict[str, float]] = {}

    def select_action(self, rule: dict[str, Any]) -> str:
        rule_id = rule.get("id", "unknown")
        actions = ["apply", "skip", "modify", "defer", "merge"]
        if rule_id not in self.q_table:
            self.q_table[rule_id] = {a: 0.0 for a in actions}
        if self._rng.random() < self.epsilon:
            return self._rng.choice(actions)
        q_values = self.q_table[rule_id]
        return max(q_values, key=q_values.get)

    def update(self, rule_id: str, action: str, reward: float) -> None:
        if rule_id not in self.q_table:
            actions = ["apply", "skip", "modify", "defer", "merge"]
            self.q_table[rule_id] = {a: 0.0 for a in actions}
        current_q = self.q_table[rule_id].get(action, 0.0)
        self.q_table[rule_id][action] = current_q + self.lr * (reward - current_q)

    def get_action_probs(self, rule_id: str) -> dict[str, float]:
        if rule_id not in self.q_table:
            actions = ["apply", "skip", "modify", "defer", "merge"]
            return {a: 0.2 for a in actions}
        q_values = self.q_table[rule_id]
        total = sum(max(v, 0) + 1e-6 for v in q_values.values())
        return {a: (max(v, 0) + 1e-6) / total for a, v in q_values.items()}

    def get_best_action(self, rule_id: str) -> str:
        q_vals = self.q_table.get(rule_id, {})
        if not q_vals:
            return "apply"
        return max(q_vals, key=lambda k: q_vals.get(k, 0))

    def reset(self) -> None:
        self.q_table.clear()
