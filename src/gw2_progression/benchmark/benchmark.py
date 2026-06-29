from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Any

from gw2_progression.benchmark.agents import Agent
from gw2_progression.benchmark.elo import GW2ELO


@dataclass
class EvaluationResult:
    agent_id: str
    agent_name: str
    agent_type: str
    economy_score: float
    decision_score: float
    simulation_score: float
    reasoning_score: float
    overall_score: float
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "agent_type": self.agent_type,
            "economy_score": round(self.economy_score, 4),
            "decision_score": round(self.decision_score, 4),
            "simulation_score": round(self.simulation_score, 4),
            "reasoning_score": round(self.reasoning_score, 4),
            "overall_score": round(self.overall_score, 4),
            "details": self.details,
        }


class BenchmarkReport:
    def __init__(self, elo_system: GW2ELO | None = None) -> None:
        self.elo = elo_system or GW2ELO()

    def generate(self, agents: list[Agent], match_history: list[dict[str, Any]]) -> dict[str, Any]:
        results = self._evaluate_all(agents, match_history)
        ranking = sorted(results, key=lambda r: r.overall_score, reverse=True)
        return {
            "ranking": [r.to_dict() for r in ranking],
            "economy_impact": self._compute_economy_impact(results),
            "reasoning_score": self._compute_reasoning(results),
            "simulation_score": self._compute_simulation(results),
            "market_analysis": self._market_analysis(match_history),
        }

    def _evaluate_all(self, agents: list[Agent], match_history: list[dict[str, Any]]) -> list[EvaluationResult]:
        results: list[EvaluationResult] = []
        for agent in agents:
            agent_history = [h for h in match_history if h.get("agent") == agent.id]
            economy_score = self._economy_score(agent, agent_history)
            decision_score = self._decision_score(agent, agent_history)
            simulation_score = self._simulation_score(agent, agent_history)
            reasoning_score = self._reasoning_score(agent, agent_history)
            overall = (economy_score + decision_score + simulation_score + reasoning_score) / 4
            results.append(EvaluationResult(
                agent_id=agent.id,
                agent_name=agent.name,
                agent_type=agent.agent_type,
                economy_score=economy_score,
                decision_score=decision_score,
                simulation_score=simulation_score,
                reasoning_score=reasoning_score,
                overall_score=overall,
                details={
                    "total_reward": agent.total_reward,
                    "actions_taken": len(agent_history),
                    "rating": agent.rating.to_dict(),
                },
            ))
        return results

    def _economy_score(self, agent: Agent, history: list[dict[str, Any]]) -> float:
        if not history:
            return 0.5
        rewards = [h.get("reward", {}).get("score", 0) for h in history]
        total = sum(rewards)
        market_actions = sum(1 for h in history if h.get("action", {}).get("type") in ("trade", "flip"))
        return min((total / max(len(history), 1)) * 2 + market_actions * 0.05, 1.0)

    def _decision_score(self, agent: Agent, history: list[dict[str, Any]]) -> float:
        if not history:
            return 0.5
        action_types = [h.get("action", {}).get("type") for h in history]
        unique_types = len(set(action_types))
        diversity = min(unique_types / 5, 1.0)
        reward_trend = 0.0
        if len(history) >= 2:
            first_half = sum(h.get("reward", {}).get("score", 0) for h in history[:len(history)//2])
            second_half = sum(h.get("reward", {}).get("score", 0) for h in history[len(history)//2:])
            reward_trend = min(max((second_half - first_half) / max(abs(first_half) + 1, 1) * 0.5, 0), 1.0)
        return (diversity * 0.6 + reward_trend * 0.4)

    def _simulation_score(self, agent: Agent, history: list[dict[str, Any]]) -> float:
        if not history:
            return 0.5
        interaction_rate = min(len(history) / 10, 1.0)
        rewards = [h.get("reward", {}).get("score", 0) for h in history]
        consistency = 1.0 - min(statistics.stdev(rewards) if len(rewards) > 1 else 0, 1.0)
        return (interaction_rate * 0.5 + consistency * 0.5)

    def _reasoning_score(self, agent: Agent, history: list[dict[str, Any]]) -> float:
        if not history:
            return 0.5
        actions = [h.get("action", {}) for h in history]
        action_types = set(a.get("type") for a in actions if a.get("type"))
        strategy_shifts = len(action_types)
        adaptability = min(strategy_shifts / 3, 1.0)
        reward_consistency = 0.5
        rewards = [h.get("reward", {}).get("score", 0) for h in history]
        if len(rewards) > 1:
            reward_consistency = 1.0 - min(statistics.stdev(rewards) * 2, 1.0)
        return (adaptability * 0.7 + reward_consistency * 0.3)

    def _compute_economy_impact(self, results: list[EvaluationResult]) -> dict[str, Any]:
        if not results:
            return {"total_impact": 0, "avg_economy_score": 0}
        avg = sum(r.economy_score for r in results) / len(results)
        return {
            "total_impact": round(sum(r.economy_score for r in results), 4),
            "avg_economy_score": round(avg, 4),
            "top_economy_agent": max(results, key=lambda r: r.economy_score).agent_name,
        }

    def _compute_reasoning(self, results: list[EvaluationResult]) -> dict[str, Any]:
        if not results:
            return {"avg_reasoning": 0, "top_reasoning_agent": ""}
        avg = sum(r.reasoning_score for r in results) / len(results)
        return {
            "avg_reasoning": round(avg, 4),
            "top_reasoning_agent": max(results, key=lambda r: r.reasoning_score).agent_name,
        }

    def _compute_simulation(self, results: list[EvaluationResult]) -> dict[str, Any]:
        if not results:
            return {"avg_simulation": 0, "top_simulation_agent": ""}
        avg = sum(r.simulation_score for r in results) / len(results)
        return {
            "avg_simulation": round(avg, 4),
            "top_simulation_agent": max(results, key=lambda r: r.simulation_score).agent_name,
        }

    def _market_analysis(self, match_history: list[dict[str, Any]]) -> dict[str, Any]:
        items_traded = set()
        action_counts: dict[str, int] = {}
        for h in match_history:
            action = h.get("action", {})
            item_id = action.get("item_id")
            action_type = action.get("type")
            if item_id:
                items_traded.add(item_id)
            if action_type:
                action_counts[action_type] = action_counts.get(action_type, 0) + 1
        return {
            "unique_items_traded": len(items_traded),
            "total_actions": len(match_history),
            "action_breakdown": action_counts,
        }
