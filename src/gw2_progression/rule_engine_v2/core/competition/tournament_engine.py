from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from gw2_progression.rule_engine_v2.core.competition.ranking_system import RuleRankingSystem
from gw2_progression.rule_engine_v2.core.competition.rule_agents import RuleAgent


@dataclass
class TournamentMatch:
    id: str
    agents: list[RuleAgent]
    world: dict[str, Any]
    scores: dict[str, float] = field(default_factory=dict)
    winner: str | None = None
    completed: bool = False
    timestamp: str = ""


class RuleTournament:
    def __init__(self, ranking: RuleRankingSystem | None = None) -> None:
        self.ranking = ranking or RuleRankingSystem()
        self.matches: list[TournamentMatch] = []
        self._rng = random.Random(1)

    def run(self, agents: list[RuleAgent], world: dict[str, Any]) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for i in range(len(agents)):
            for j in range(i + 1, len(agents)):
                match = self._run_match(agents[i], agents[j], world)
                self.matches.append(match)
                results.append({
                    "match_id": match.id,
                    "agent_a": agents[i].id,
                    "agent_b": agents[j].id,
                    "scores": match.scores,
                    "winner": match.winner,
                })
                agents[i].total_matches += 1
                agents[j].total_matches += 1
                if match.winner == agents[i].id:
                    agents[i].wins += 1
                elif match.winner == agents[j].id:
                    agents[j].wins += 1
        self.ranking.update(agents, results)
        return results

    def _run_match(self, agent_a: RuleAgent, agent_b: RuleAgent, world: dict[str, Any]) -> TournamentMatch:
        world_a = agent_a.apply_rules(dict(world))
        world_b = agent_b.apply_rules(dict(world))
        score_a = agent_a.evaluate(world_b)
        score_b = agent_b.evaluate(world_a)
        scores = {agent_a.id: score_a, agent_b.id: score_b}
        winner = agent_a.id if score_a > score_b else agent_b.id if score_b > score_a else None
        return TournamentMatch(
            id=f"match:{uuid.uuid4().hex[:8]}",
            agents=[agent_a, agent_b],
            world=world,
            scores=scores,
            winner=winner,
            completed=True,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def run_championship(self, agents: list[RuleAgent], world: dict[str, Any], rounds: int = 3) -> dict[str, Any]:
        all_results: list[dict[str, Any]] = []
        for r in range(rounds):
            round_results = self.run(agents, world)
            all_results.extend(round_results)
        leaderboard = self.ranking.leaderboard(agents)
        return {
            "tournament_id": f"championship:{uuid.uuid4().hex[:8]}",
            "rounds": rounds,
            "total_matches": len(all_results),
            "results": all_results,
            "leaderboard": leaderboard,
        }

    def rank(self, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        agent_scores: dict[str, float] = {}
        for r in results:
            for aid, score in r.get("scores", {}).items():
                agent_scores[aid] = agent_scores.get(aid, 0) + score
        sorted_agents = sorted(agent_scores.items(), key=lambda x: x[1], reverse=True)
        return [
            {"rank": i + 1, "agent_id": aid, "total_score": round(score, 4)}
            for i, (aid, score) in enumerate(sorted_agents)
        ]
