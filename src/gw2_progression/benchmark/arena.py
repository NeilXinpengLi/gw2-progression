from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from gw2_progression.benchmark.agents import Agent, create_default_agent_roster
from gw2_progression.benchmark.benchmark import BenchmarkReport
from gw2_progression.benchmark.economy import EconomyEngine
from gw2_progression.benchmark.elo import GW2ELO
from gw2_progression.benchmark.evolution import EvolutionEngine
from gw2_progression.benchmark.self_play import ArenaWorld, SelfPlayEngine
from gw2_progression.benchmark.tournament import Leaderboard, TournamentOrchestrator


class Arena:
    def __init__(self, seed: int = 1) -> None:
        self.seed = seed
        self.elo = GW2ELO()
        self.leaderboard = Leaderboard(elo_system=self.elo)
        self.tournament = TournamentOrchestrator(elo_system=self.elo)
        self.evolution = EvolutionEngine(elo_system=self.elo)
        self.benchmark = BenchmarkReport(elo_system=self.elo)
        self.self_play = SelfPlayEngine()
        self.economy = EconomyEngine(seed=seed)
        self.agents: dict[str, Agent] = {}
        self.arena_id = f"arena:{uuid.uuid4().hex[:8]}"

    def register_agent(self, agent: Agent) -> None:
        self.agents[agent.id] = agent
        self.leaderboard.register(agent)

    def register_default_roster(self) -> list[Agent]:
        agents = create_default_agent_roster()
        for agent in agents:
            self.register_agent(agent)
        return agents

    def run_match(self, agent_ids: list[str] | None = None, max_steps: int = 50) -> dict[str, Any]:
        agents = self._resolve_agents(agent_ids)
        world = ArenaWorld(max_steps=max_steps, seed=self.seed)
        history = self.self_play.run_match(agents, world=world)
        for agent in agents:
            self.leaderboard.sync_ratings([agent])
        report = self.benchmark.generate(agents, history)
        return {
            "arena_id": self.arena_id,
            "match_id": f"match:{uuid.uuid4().hex[:8]}",
            "agents": [{"id": a.id, "name": a.name, "type": a.agent_type} for a in agents],
            "world_snapshot": world.snapshot(),
            "history": history,
            "report": report,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def run_simulation(self, ticks: int = 50, agent_ids: list[str] | None = None) -> dict[str, Any]:
        agents = self._resolve_agents(agent_ids)
        self.economy.reset(self.seed)
        simulation_history: list[dict[str, Any]] = []
        for t in range(ticks):
            for agent in agents:
                state = {
                    "market": self.economy.market_snapshot(),
                    "step": t,
                    "max_steps": ticks,
                    "agent_id": agent.id,
                    "agent_gold": 1000 + agent.total_reward * 100,
                }
                action = agent.act(state)
                item_id = action.get("item_id")
                action_type = action.get("type")
                qty = int(action.get("quantity", 1))
                if action_type == "trade" and item_id:
                    result = self.economy.apply_trade(item_id, qty, buyer=agent.id)
                elif action_type == "craft" and item_id:
                    result = self.economy.apply_craft(item_id, action.get("consumes", {}), crafter=agent.id)
                elif action_type in ("farm", "collect") and item_id:
                    result = self.economy.apply_farm(item_id, qty, farmer=agent.id)
                else:
                    result = {"score": 0, "item_id": item_id}
                score = self.economy.competitive_score(agent.id, [action])
                reward = {"score": round(score, 4), "action": action, "item_id": item_id}
                agent.observe(reward)
                simulation_history.append({
                    "agent": agent.id,
                    "agent_name": agent.name,
                    "action": action,
                    "reward": reward,
                    "result": result,
                    "t": t,
                })
        report = self.benchmark.generate(agents, simulation_history)
        return {
            "arena_id": self.arena_id,
            "simulation_id": f"sim:{uuid.uuid4().hex[:8]}",
            "ticks": ticks,
            "agents": [{"id": a.id, "name": a.name, "type": a.agent_type} for a in agents],
            "final_market": self.economy.market_snapshot(),
            "history": simulation_history[-20:] if len(simulation_history) > 20 else simulation_history,
            "report": report,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def run_evolution(self, generations: int = 3) -> dict[str, Any]:
        if not self.agents:
            self.register_default_roster()
        current_population = list(self.agents.values())
        evolution_history: list[dict[str, Any]] = []
        for gen in range(generations):
            current_population = self.evolution.evolve(current_population)
            for agent in current_population:
                self.register_agent(agent)
            evolution_history.append({
                "generation": gen + 1,
                "population_size": len(current_population),
                "avg_rating": round(sum(a.rating.overall for a in current_population) / len(current_population), 1) if current_population else 0,
            })
        self.leaderboard.sync_ratings(current_population)
        return {
            "arena_id": self.arena_id,
            "generations": generations,
            "evolution_history": evolution_history,
            "final_population": [{"id": a.id, "name": a.name, "type": a.agent_type, "rating": a.rating.to_dict()} for a in current_population],
            "leaderboard": self.leaderboard.get_ranking(),
        }

    def run_tournament(self, agent_ids: list[str] | None = None, max_steps: int = 50, rounds: int = 1) -> dict[str, Any]:
        agents = self._resolve_agents(agent_ids)
        result = self.tournament.run_tournament(agents, max_steps=max_steps, rounds=rounds)
        result["arena_id"] = self.arena_id
        return result

    def get_leaderboard(self, sort_by: str = "overall") -> list[dict[str, Any]]:
        return self.leaderboard.get_ranking(sort_by=sort_by)

    def economy_update(self, item_updates: dict[str, dict[str, float]]) -> dict[str, Any]:
        for item_id, patch in item_updates.items():
            if item_id in self.economy.items:
                item = self.economy.items[item_id]
                for key, value in patch.items():
                    if hasattr(item, key):
                        setattr(item, key, value)
                self.economy.update_price(item_id)
        return {"market": self.economy.market_snapshot()}

    def update_elo(self, agent_id: str, result: dict[str, Any]) -> dict[str, Any]:
        agent = self.agents.get(agent_id)
        if not agent:
            return {"error": f"Agent {agent_id} not found"}
        self.elo.update_from_history(agent, [result])
        self.leaderboard.sync_ratings([agent])
        return {"agent_id": agent_id, "new_rating": agent.rating.to_dict()}

    def _resolve_agents(self, agent_ids: list[str] | None = None) -> list[Agent]:
        if agent_ids:
            return [self.agents[aid] for aid in agent_ids if aid in self.agents]
        if not self.agents:
            self.register_default_roster()
        return list(self.agents.values())

    def snapshot(self) -> dict[str, Any]:
        return {
            "arena_id": self.arena_id,
            "agent_count": len(self.agents),
            "leaderboard": self.leaderboard.get_ranking(),
            "market": self.economy.market_snapshot(),
        }


_arena: Arena | None = None


def get_arena(seed: int = 1) -> Arena:
    global _arena
    if _arena is None:
        _arena = Arena(seed=seed)
    return _arena
