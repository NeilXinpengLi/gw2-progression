from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any


@dataclass
class PolicyDistribution:
    """A probability distribution over actions from the RL policy."""
    action_type: str
    item_id: str
    probability: float
    q_value: float
    advantage: float = 0.0


class ProbabilisticPolicy:
    """Probabilistic policy — outputs distributions over actions.

    Extends the tabular Q-learning policy to produce calibrated
    probability distributions using softmax over Q-values.

    π(a|s) = softmax(Q(s,a) / τ)

    where τ is the temperature controlling exploration vs exploitation.
    """

    def __init__(self, temperature: float = 1.0, min_probability: float = 0.01) -> None:
        self.temperature = temperature
        self.min_probability = min_probability
        self._q_table: dict[str, dict[str, float]] = {}
        self._distribution_history: list[dict[str, Any]] = []

    def get_distribution(self, state_key: str, available_actions: list[dict[str, Any]]) -> list[PolicyDistribution]:
        """Compute π(a|s) = softmax(Q(s,a) / τ) for all available actions."""
        if state_key not in self._q_table:
            self._q_table[state_key] = {}

        q_values: list[float] = []
        action_keys: list[str] = []

        for action in available_actions:
            ak = self._action_key(action)
            action_keys.append(ak)
            if ak not in self._q_table[state_key]:
                self._q_table[state_key][ak] = 0.0
            q_values.append(self._q_table[state_key][ak])

        probabilities = self._softmax(q_values, self.temperature)

        min_p = self.min_probability
        adjusted: list[float] = []
        for p in probabilities:
            adjusted.append(max(min_p, p))

        total = sum(adjusted)
        if total > 0:
            adjusted = [p / total for p in adjusted]

        distributions: list[PolicyDistribution] = []
        for action, q_val, prob in zip(available_actions, q_values, adjusted):
            mean_q = sum(q_values) / max(len(q_values), 1)
            advantage = q_val - mean_q
            distributions.append(PolicyDistribution(
                action_type=action.get("type", "unknown"),
                item_id=action.get("item_id", ""),
                probability=round(prob, 4),
                q_value=round(q_val, 4),
                advantage=round(advantage, 4),
            ))

        self._distribution_history.append({
            "state_key": state_key,
            "action_count": len(distributions),
            "max_prob": round(max(p.probability for p in distributions), 4) if distributions else 0.0,
            "entropy": round(self._distribution_entropy(distributions), 4),
        })

        distributions.sort(key=lambda d: -d.probability)
        return distributions

    def update(self, state_key: str, action: dict[str, Any], reward: float, learning_rate: float = 0.1) -> None:
        """Q-learning update: Q(s,a) += α * (reward - Q(s,a))."""
        if state_key not in self._q_table:
            self._q_table[state_key] = {}
        ak = self._action_key(action)
        current = self._q_table[state_key].get(ak, 0.0)
        self._q_table[state_key][ak] = current + learning_rate * (reward - current)

    def sample_action(self, state_key: str, available_actions: list[dict[str, Any]], rng: random.Random | None = None) -> dict[str, Any]:
        """Sample an action from the policy distribution."""
        dist = self.get_distribution(state_key, available_actions)
        rng = rng or random.Random()
        actions = list(dist)
        weights = [d.probability for d in actions]
        chosen = rng.choices(actions, weights=weights, k=1)[0]
        for action in available_actions:
            if action.get("type") == chosen.action_type and action.get("item_id", "") == chosen.item_id:
                return action
        return available_actions[0] if available_actions else {"type": "farm", "item_id": "gold", "quantity": 1}

    def set_temperature(self, temperature: float) -> None:
        self.temperature = max(0.01, temperature)

    def _softmax(self, values: list[float], temperature: float) -> list[float]:
        if not values:
            return []
        scaled = [v / max(temperature, 1e-10) for v in values]
        max_s = max(scaled) if scaled else 0.0
        exp_vals = [math.exp(v - max_s) for v in scaled]
        total = sum(exp_vals)
        if total > 0:
            return [v / total for v in exp_vals]
        return [1.0 / len(values)] * len(values)

    def _distribution_entropy(self, dist: list[PolicyDistribution]) -> float:
        n = len(dist)
        if n <= 1:
            return 0.0
        h = 0.0
        for d in dist:
            if d.probability > 0:
                h -= d.probability * math.log2(d.probability)
        return h / math.log2(n)

    def _action_key(self, action: dict[str, Any]) -> str:
        return f"{action.get('type', '')}:{action.get('item_id', '')}"

    @property
    def average_q(self) -> float:
        if not self._q_table:
            return 0.0
        all_qs = [q for state_qs in self._q_table.values() for q in state_qs.values()]
        return sum(all_qs) / max(len(all_qs), 1) if all_qs else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "temperature": self.temperature,
            "min_probability": self.min_probability,
            "average_q": round(self.average_q, 4),
            "state_count": len(self._q_table),
            "total_actions": sum(len(qs) for qs in self._q_table.values()),
            "last_entropy": self._distribution_history[-1]["entropy"] if self._distribution_history else None,
        }
