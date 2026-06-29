from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from gw2_progression.rule_engine_v2.core.competition.rule_agents import RuleAgent, create_rule_agent
from gw2_progression.rule_engine_v2.core.competition.tournament_engine import RuleTournament
from gw2_progression.rule_engine_v2.core.evolution.survival_engine import RuleEvolutionSystem
from gw2_progression.rule_engine_v2.core.gnn.rule_graph_model import RuleGNN
from gw2_progression.rule_engine_v2.core.llm.reasoning_compressor import ReasoningCompressor
from gw2_progression.rule_engine_v2.core.llm.rule_distiller import RuleDistiller
from gw2_progression.rule_engine_v2.core.rl.reward_engine import RuleReward
from gw2_progression.rule_engine_v2.core.rl.rule_optimizer import RuleOptimizer
from gw2_progression.rule_engine_v2.simulation.economy_sim import EconomySim
from gw2_progression.rule_engine_v2.simulation.gw2_world_sim import GW2WorldSim


class RuleEngineV2:
    def __init__(self) -> None:
        self.gnn = RuleGNN()
        self.optimizer = RuleOptimizer()
        self.reward = RuleReward()
        self.distiller = RuleDistiller()
        self.compressor = ReasoningCompressor()
        self.evolution = RuleEvolutionSystem()
        self.tournament = RuleTournament()
        self.world_sim = GW2WorldSim()
        self.economy_sim = EconomySim()
        self.rules: list[dict[str, Any]] = []
        self.agents: list[RuleAgent] = []

    def extract_rules(self, data: dict[str, Any] | list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        if data is None:
            self.rules = self.evolution._seed_population()[:10]
        elif isinstance(data, list):
            self.rules = data
        elif isinstance(data, dict):
            self.rules = data.get("rules", [])
        return self.rules

    def encode_rules_gnn(self) -> dict[str, list[float]]:
        return self.gnn.get_embeddings(self.rules)

    def simulate_rules(self, steps: int = 10) -> dict[str, Any]:
        world_results = self.world_sim.step_batch(self.rules, steps=steps)
        economy_results = self.economy_sim.simulate(self.rules, steps=steps)
        return {
            "world_states": [w.to_dict() for w in world_results],
            "economy_snapshots": economy_results,
            "economy_metrics": self.economy_sim.get_metrics(),
            "steps": steps,
        }

    def evaluate_rules(self) -> list[dict[str, float]]:
        return self.reward.compute_batch(self.rules)

    def optimize_rules(self) -> list[dict[str, Any]]:
        self.rules = self.optimizer.update(self.rules)
        return self.rules

    def distill_rules(self) -> list[dict[str, Any]]:
        distilled = self.distiller.distill(self.rules)
        return [d.to_dict() for d in distilled]

    def compress_reasoning(self, chains: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
        return [c.__dict__ for c in self.compressor.compress_batch(chains)]

    def compete_rules(self) -> dict[str, Any]:
        if not self.agents:
            self.agents = [
                create_rule_agent("Alpha", rules=self.rules[:max(1, len(self.rules)//2)]),
                create_rule_agent("Beta", rules=self.rules[max(1, len(self.rules)//2):] if len(self.rules) > 1 else self.rules),
            ]
            for i in range(2, 5):
                if i < len(self.rules):
                    self.agents.append(create_rule_agent(f"Agent_{i}", rules=[self.rules[i]]))
        world = self.world_sim.state.to_dict()
        result = self.tournament.run_championship(self.agents, world, rounds=2)
        for agent in self.agents:
            for r in agent.rules:
                r["agent_fitness"] = agent.fitness
        return result

    def evolve_rules(self) -> list[dict[str, Any]]:
        self.rules = self.evolution.evolve(self.rules)
        return self.rules

    def run_full_pipeline(self) -> dict[str, Any]:
        gnn_embeddings = self.encode_rules_gnn()
        sim_result = self.simulate_rules(steps=5)
        eval_result = self.evaluate_rules()
        optimize_result = self.optimize_rules()
        distill_result = self.distill_rules()
        compete_result = self.compete_rules()
        evolve_result = self.evolve_rules()
        return {
            "pipeline_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "steps": {
                "gnn_encoding": {"rule_count": len(self.rules), "embeddings": {k: len(v) for k, v in gnn_embeddings.items()}},
                "simulation": {"steps": 5, "economy_metrics": sim_result["economy_metrics"]},
                "evaluation": eval_result,
                "optimization": {"rule_count": len(optimize_result)},
                "distillation": {"rule_count": len(distill_result)},
                "competition": {"matches": compete_result.get("total_matches", 0)},
                "evolution": {"generation": self.evolution.generation, "population": len(evolve_result)},
            },
            "evolution_history": self.evolution.history,
            "leaderboard": compete_result.get("leaderboard", []),
        }


_engine: RuleEngineV2 | None = None


def get_rule_engine() -> RuleEngineV2:
    global _engine
    if _engine is None:
        _engine = RuleEngineV2()
    return _engine
