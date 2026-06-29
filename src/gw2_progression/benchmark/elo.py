from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class EloRating:
    skill: float = 1200.0
    economic: float = 1200.0
    reasoning: float = 1200.0
    games_played: int = 0

    @property
    def overall(self) -> float:
        return round((self.skill + self.economic + self.reasoning) / 3, 1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill": round(self.skill, 1),
            "economic": round(self.economic, 1),
            "reasoning": round(self.reasoning, 1),
            "overall": self.overall,
            "games_played": self.games_played,
        }


K_FACTOR = 32
DIMENSION_WEIGHTS = {
    "profit": 0.3,
    "efficiency": 0.3,
    "reasoning": 0.2,
    "stability": 0.2,
}


class GW2ELO:
    def __init__(self, k_factor: float = K_FACTOR) -> None:
        self.k = k_factor
        self.history: list[dict[str, Any]] = []

    def _expected_score(self, rating_a: float, rating_b: float) -> float:
        return 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0))

    def _update_rating(self, current: float, expected: float, actual: float) -> float:
        return current + self.k * (actual - expected)

    def update(self, agent_a: Any, agent_b: Any, result: dict[str, Any]) -> dict[str, Any]:
        score = (
            DIMENSION_WEIGHTS["profit"] * result.get("profit", 0)
            + DIMENSION_WEIGHTS["efficiency"] * result.get("efficiency", 0)
            + DIMENSION_WEIGHTS["reasoning"] * result.get("reasoning", 0)
            + DIMENSION_WEIGHTS["stability"] * result.get("stability", 0)
        )
        actual_a = min(max(score, 0), 1)
        actual_b = 1 - actual_a
        expected_a = self._expected_score(agent_a.rating.skill, agent_b.rating.skill)
        expected_b = 1 - expected_a
        agent_a.rating.skill = self._update_rating(agent_a.rating.skill, expected_a, actual_a)
        agent_b.rating.skill = self._update_rating(agent_b.rating.skill, expected_b, actual_b)
        agent_a.rating.economic = self._update_rating(agent_a.rating.economic, expected_a, result.get("profit", 0) * 2)
        agent_b.rating.economic = self._update_rating(agent_b.rating.economic, expected_b, result.get("profit", 0) * 2)
        agent_a.rating.reasoning = self._update_rating(agent_a.rating.reasoning, expected_a, result.get("reasoning", 0) * 3)
        agent_b.rating.reasoning = self._update_rating(agent_b.rating.reasoning, expected_b, result.get("reasoning", 0) * 3)
        agent_a.rating.games_played += 1
        agent_b.rating.games_played += 1
        delta = {
            "agent_a": agent_a.id,
            "agent_b": agent_b.id,
            "score": round(score, 4),
            "actual_a": round(actual_a, 4),
            "actual_b": round(actual_b, 4),
            "expected_a": round(expected_a, 4),
            "expected_b": round(expected_b, 4),
            "rating_delta_a": round(agent_a.rating.skill - (agent_a.rating.skill - self.k * (actual_a - expected_a)), 1),
            "rating_delta_b": round(agent_b.rating.skill - (agent_b.rating.skill - self.k * (actual_b - expected_b)), 1),
        }
        self.history.append(delta)
        return delta

    def update_from_history(self, agent: Any, match_history: list[dict[str, Any]]) -> dict[str, Any]:
        total_profit = sum(h.get("reward", {}).get("score", 0) for h in match_history)
        actions = [h.get("action", {}) for h in match_history]
        varied_actions = len(set(a.get("type") for a in actions if a.get("type")))
        efficiency = min(len(match_history) / max(getattr(agent, '_world_max_steps', 100), 1), 1.0)
        reasoning = min(varied_actions / 5, 1.0)
        profit = min(max(total_profit, 0), 1.0)
        rewards = [h.get("reward", {}).get("score", 0) for h in match_history]
        stability = 1.0 - min(float(np.std(rewards)) if len(rewards) > 1 else 0, 1.0) if match_history else 0.5
        result = {
            "profit": profit,
            "efficiency": efficiency,
            "reasoning": reasoning,
            "stability": stability,
        }
        agent.rating.skill = self._update_rating(agent.rating.skill, 0.5, profit)
        agent.rating.economic = self._update_rating(agent.rating.economic, 0.5, profit * 2)
        agent.rating.reasoning = self._update_rating(agent.rating.reasoning, 0.5, reasoning * 3)
        agent.rating.games_played += 1
        return result

    def leaderboard(self, agents: list[Any]) -> list[dict[str, Any]]:
        sorted_agents = sorted(agents, key=lambda a: a.rating.overall, reverse=True)
        return [
            {
                "rank": idx + 1,
                "id": a.id,
                "name": a.name,
                "type": a.agent_type,
                "rating": a.rating.to_dict(),
            }
            for idx, a in enumerate(sorted_agents)
        ]
