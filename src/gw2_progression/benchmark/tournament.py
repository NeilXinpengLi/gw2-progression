from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from gw2_progression.benchmark.agents import Agent
from gw2_progression.benchmark.elo import GW2ELO
from gw2_progression.benchmark.self_play import ArenaWorld, SelfPlayEngine


@dataclass
class TournamentMatch:
    id: str
    agents: list[Agent]
    world_seed: int
    max_steps: int = 50
    history: list[dict[str, Any]] = field(default_factory=list)
    result: dict[str, Any] | None = None
    completed: bool = False
    started_at: str = ""
    completed_at: str = ""


class Leaderboard:
    def __init__(self, elo_system: GW2ELO | None = None) -> None:
        self.elo = elo_system or GW2ELO()
        self.entries: dict[str, dict[str, Any]] = {}

    def register(self, agent: Agent) -> None:
        if agent.id not in self.entries:
            self.entries[agent.id] = {
                "agent_id": agent.id,
                "name": agent.name,
                "type": agent.agent_type,
                "rating": agent.rating.to_dict(),
                "matches": 0,
                "wins": 0,
                "total_score": 0.0,
            }

    def record_match(self, agent_id: str, score: float, won: bool = False) -> None:
        if agent_id in self.entries:
            self.entries[agent_id]["matches"] += 1
            self.entries[agent_id]["wins"] += 1 if won else 0
            self.entries[agent_id]["total_score"] += score
            entry = self.entries[agent_id]
            entry["rating"] = entry.get("rating", {})

    def sync_ratings(self, agents: list[Agent]) -> None:
        for agent in agents:
            if agent.id in self.entries:
                self.entries[agent.id]["rating"] = agent.rating.to_dict()

    def get_ranking(self, sort_by: str = "overall") -> list[dict[str, Any]]:
        entries = list(self.entries.values())
        if sort_by == "overall":
            entries.sort(key=lambda e: e.get("rating", {}).get("overall", 1200), reverse=True)
        elif sort_by == "skill":
            entries.sort(key=lambda e: e.get("rating", {}).get("skill", 1200), reverse=True)
        elif sort_by == "economic":
            entries.sort(key=lambda e: e.get("rating", {}).get("economic", 1200), reverse=True)
        elif sort_by == "reasoning":
            entries.sort(key=lambda e: e.get("rating", {}).get("reasoning", 1200), reverse=True)
        elif sort_by == "wins":
            entries.sort(key=lambda e: e.get("wins", 0), reverse=True)
        for idx, entry in enumerate(entries):
            entry["rank"] = idx + 1
        return entries


class TournamentOrchestrator:
    def __init__(self, elo_system: GW2ELO | None = None) -> None:
        self.elo = elo_system or GW2ELO()
        self.leaderboard = Leaderboard(elo_system=self.elo)
        self.engine = SelfPlayEngine()
        self.matches: list[TournamentMatch] = []
        self._rng = random.Random()

    def register_agent(self, agent: Agent) -> None:
        self.leaderboard.register(agent)

    def register_agents(self, agents: list[Agent]) -> None:
        for agent in agents:
            self.register_agent(agent)

    def create_match(self, agents: list[Agent], max_steps: int = 50) -> TournamentMatch:
        match = TournamentMatch(
            id=f"match:{uuid.uuid4().hex[:8]}",
            agents=agents,
            world_seed=self._rng.randint(1, 10000),
            max_steps=max_steps,
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        self.matches.append(match)
        return match

    def run_match(self, match: TournamentMatch) -> TournamentMatch:
        world = ArenaWorld(max_steps=match.max_steps, seed=match.world_seed)
        history = self.engine.run_match(match.agents, world=world)
        match.history = history
        scores: dict[str, float] = {}
        for agent in match.agents:
            agent_scores = [h.get("reward", {}).get("score", 0) for h in history if h["agent"] == agent.id]
            scores[agent.id] = sum(agent_scores)
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        match.result = {
            "scores": scores,
            "winner": sorted_scores[0][0] if sorted_scores else None,
            "winner_score": sorted_scores[0][1] if sorted_scores else 0,
            "ranking": [{"agent_id": aid, "score": round(scr, 4)} for aid, scr in sorted_scores],
        }
        if len(match.agents) == 2 and match.result["winner"]:
            a1, a2 = match.agents
            s1 = match.result["scores"].get(a1.id, 0)
            s2 = match.result["scores"].get(a2.id, 0)
            score_val = s1 / max(s1 + s2, 1)
            self.elo.update(a1, a2, {"profit": score_val, "efficiency": 0.5, "reasoning": 0.5, "stability": 0.5})
        for agent in match.agents:
            agent_score = scores.get(agent.id, 0)
            all_scores_list = list(scores.values())
            won = agent.id == match.result.get("winner") if all_scores_list else False
            self.leaderboard.record_match(agent.id, agent_score, won=won)
        self.leaderboard.sync_ratings(match.agents)
        match.completed = True
        match.completed_at = datetime.now(timezone.utc).isoformat()
        return match

    def run_round_robin(self, agents: list[Agent], max_steps: int = 50) -> list[TournamentMatch]:
        self.register_agents(agents)
        completed: list[TournamentMatch] = []
        for i in range(len(agents)):
            for j in range(i + 1, len(agents)):
                match = self.create_match([agents[i], agents[j]], max_steps=max_steps)
                self.run_match(match)
                completed.append(match)
        return completed

    def run_tournament(self, agents: list[Agent], max_steps: int = 50, rounds: int = 1) -> dict[str, Any]:
        self.register_agents(agents)
        all_matches: list[TournamentMatch] = []
        for r in range(rounds):
            round_matches = self.run_round_robin(agents, max_steps=max_steps)
            all_matches.extend(round_matches)
        ranking = self.leaderboard.get_ranking()
        return {
            "tournament_id": f"tournament:{uuid.uuid4().hex[:8]}",
            "rounds": rounds,
            "total_matches": len(all_matches),
            "matches": [
                {
                    "id": m.id,
                    "agents": [a.id for a in m.agents],
                    "winner": m.result.get("winner") if m.result else None,
                    "completed": m.completed,
                }
                for m in all_matches
            ],
            "leaderboard": ranking,
        }
