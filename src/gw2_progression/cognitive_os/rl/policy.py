from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any


@dataclass
class PolicyStep:
    action_type: str
    item_id: str
    quantity: int
    q_value: float = 0.0
    confidence: float = 0.0


class RLPolicy:
    """Tabular Q-learning policy for GW2 action selection.

    State → Action mapping with epsilon-greedy exploration.
    Supports action types: farm, gather, collect, trade, craft, achievement.
    """

    def __init__(
        self,
        learning_rate: float = 0.1,
        discount_factor: float = 0.95,
        epsilon: float = 0.2,
        epsilon_decay: float = 0.995,
        min_epsilon: float = 0.01,
    ) -> None:
        self.lr = learning_rate
        self.gamma = discount_factor
        self.epsilon = epsilon
        self.epsilon_decay = epsilon_decay
        self.min_epsilon = min_epsilon
        self.q_table: dict[str, dict[str, float]] = {}
        self._visit_counts: dict[str, dict[str, int]] = {}
        self._training_steps: int = 0

    def _state_key(self, state: dict[str, Any]) -> str:
        inventory = state.get("inventory", {}) or {}
        top_items = sorted(inventory.items(), key=lambda x: -x[1])[:5]
        item_part = ":".join(f"{k}-{v}" for k, v in top_items)
        gold = int(float(state.get("gold", 0)))
        ach_count = len(state.get("achievements", []) or [])
        return f"g{gold}_a{ach_count}_{hash(item_part) % 10000}"

    def _action_key(self, action: dict[str, Any]) -> str:
        return f"{action.get('type', '')}:{action.get('item_id', '')}"

    def get_q(self, state_key: str, action_key: str) -> float:
        return self.q_table.get(state_key, {}).get(action_key, 0.0)

    def set_q(self, state_key: str, action_key: str, value: float) -> None:
        if state_key not in self.q_table:
            self.q_table[state_key] = {}
        self.q_table[state_key][action_key] = value

    def _increment_visit(self, state_key: str, action_key: str) -> None:
        if state_key not in self._visit_counts:
            self._visit_counts[state_key] = {}
        self._visit_counts[state_key][action_key] = self._visit_counts[state_key].get(action_key, 0) + 1

    def select_action(
        self,
        state: dict[str, Any],
        available_actions: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        if not available_actions:
            return None
        state_key = self._state_key(state)

        if random.random() < self.epsilon:
            chosen = random.choice(available_actions)
            return chosen

        best_action: dict[str, Any] | None = None
        best_q = float("-inf")
        for action in available_actions:
            ak = self._action_key(action)
            q = self.get_q(state_key, ak)
            confidence = self._get_confidence(state_key, ak)
            if q + confidence > best_q:
                best_q = q + confidence
                best_action = action
        return best_action or random.choice(available_actions)

    def _get_confidence(self, state_key: str, action_key: str) -> float:
        counts = self._visit_counts.get(state_key, {})
        n = counts.get(action_key, 0)
        return min(1.0, n / 50.0) * 0.1

    def update(
        self,
        state: dict[str, Any],
        action: dict[str, Any],
        reward: float,
        next_state: dict[str, Any],
        available_actions: list[dict[str, Any]],
    ) -> None:
        state_key = self._state_key(state)
        action_key = self._action_key(action)
        next_state_key = self._state_key(next_state)

        current_q = self.get_q(state_key, action_key)
        max_next_q = max(
            (self.get_q(next_state_key, self._action_key(a)) for a in (available_actions or [])),
            default=0.0,
        )
        new_q = current_q + self.lr * (reward + self.gamma * max_next_q - current_q)
        self.set_q(state_key, action_key, new_q)
        self._increment_visit(state_key, action_key)
        self._training_steps += 1

        if self._training_steps % 100 == 0:
            self.epsilon = max(self.min_epsilon, self.epsilon * self.epsilon_decay)

    def get_best_actions(self, state: dict[str, Any], top_n: int = 5) -> list[PolicyStep]:
        state_key = self._state_key(state)
        if state_key not in self.q_table:
            return []
        scored = [
            PolicyStep(
                action_type=ak.split(":")[0] if ":" in ak else ak,
                item_id=ak.split(":")[1] if ":" in ak and len(ak.split(":")) > 1 else "",
                quantity=1,
                q_value=q,
                confidence=self._get_confidence(state_key, ak),
            )
            for ak, q in sorted(self.q_table[state_key].items(), key=lambda x: -x[1])[:top_n]
        ]
        return scored

    def to_dict(self) -> dict[str, Any]:
        return {
            "learning_rate": self.lr,
            "discount_factor": self.gamma,
            "epsilon": self.epsilon,
            "training_steps": self._training_steps,
            "q_table_size": sum(len(actions) for actions in self.q_table.values()),
            "state_count": len(self.q_table),
        }
