from __future__ import annotations

from typing import Any

from gw2_progression.rule_engine_v2.core.competition.rule_agents import RuleAgent


class RuleRankingSystem:
    def __init__(self, k_factor: float = 32) -> None:
        self.k = k_factor
        self.ratings: dict[str, dict[str, float]] = {}

    def initialize(self, agent: RuleAgent) -> None:
        if agent.id not in self.ratings:
            self.ratings[agent.id] = {
                "elo": 1200.0,
                "rule_diversity": 0.0,
                "adaptability": 0.0,
                "consistency": 0.0,
                "peak_fitness": 0.0,
            }

    def update(self, agents: list[RuleAgent], results: list[dict[str, Any]]) -> None:
        for agent in agents:
            self.initialize(agent)
        for r in results:
            scores = r.get("scores", {})
            winner = r.get("winner")
            for aid in scores:
                if aid in self.ratings:
                    expected = 1.0 / (1.0 + 10.0 ** ((1200 - self.ratings[aid]["elo"]) / 400.0))
                    actual = 1.0 if aid == winner else 0.0 if winner else 0.5
                    self.ratings[aid]["elo"] += self.k * (actual - expected)
        for agent in agents:
            if agent.id in self.ratings:
                self.ratings[agent.id]["rule_diversity"] = min(len(set(r.get("type", "") for r in agent.rules)) / 5, 1.0)
                self.ratings[agent.id]["adaptability"] = min(agent.win_rate * 0.7 + 0.3, 1.0)
                self.ratings[agent.id]["consistency"] = agent.win_rate if agent.total_matches > 3 else 0.5
                self.ratings[agent.id]["peak_fitness"] = max(self.ratings[agent.id]["peak_fitness"], agent.fitness)

    def leaderboard(self, agents: list[RuleAgent]) -> list[dict[str, Any]]:
        self.update(agents, [])
        ranked = sorted(
            [(a, self.ratings.get(a.id, {})) for a in agents],
            key=lambda x: x[1].get("elo", 1200),
            reverse=True,
        )
        return [
            {
                "rank": i + 1,
                "agent_id": a.id,
                "name": a.name,
                "strategy": a.strategy,
                "win_rate": round(a.win_rate, 4),
                "rule_count": len(a.rules),
                **ratings,
            }
            for i, (a, ratings) in enumerate(ranked)
        ]

    def get_rating(self, agent_id: str) -> dict[str, float]:
        return self.ratings.get(agent_id, {"elo": 1200})
