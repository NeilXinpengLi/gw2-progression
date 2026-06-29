from __future__ import annotations

import copy
import random
from dataclasses import dataclass
from typing import Any

from gw2_progression.benchmark.agents import Agent, CrafterAgent, GW2EfficiencyToolAgent, MetaStrategyAgent, RLAgent, TraderAgent
from gw2_progression.benchmark.elo import GW2ELO


@dataclass
class EvolutionConfig:
    population_size: int = 10
    elite_ratio: float = 0.3
    mutation_rate: float = 0.2
    crossover_rate: float = 0.5
    seed: int = 1


AGENT_TYPES = ["trader", "crafter", "rl", "meta", "efficiency"]


class EvolutionEngine:
    def __init__(self, config: EvolutionConfig | None = None, elo_system: GW2ELO | None = None) -> None:
        self.config = config or EvolutionConfig()
        self.elo = elo_system or GW2ELO()
        self._rng = random.Random(self.config.seed)
        self.generation = 0
        self.history: list[dict[str, Any]] = []

    def evaluate(self, population: list[Agent]) -> dict[str, float]:
        scores: dict[str, float] = {}
        for agent in population:
            rating = agent.rating
            base_score = rating.overall / 1200.0
            experience_bonus = min(rating.games_played / 10, 1.0) * 0.1
            memory_score = min(len(agent.memory) / 50, 1.0) * 0.05
            scores[agent.id] = base_score + experience_bonus + memory_score
        return scores

    def select_top(self, scores: dict[str, float], population: list[Agent]) -> list[Agent]:
        sorted_pairs = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        elite_count = max(1, int(len(population) * self.config.elite_ratio))
        selected_ids = {pair[0] for pair in sorted_pairs[:elite_count]}
        return [a for a in population if a.id in selected_ids]

    def mutate(self, agent: Agent) -> Agent:
        mutated = copy.deepcopy(agent)
        mutated.id = f"{agent.agent_type}:evolved:{self._rng.randint(1000, 9999)}"
        mutated.name = f"{agent.name}_mutated_gen{self.generation}"
        mutated.rating.skill += self._rng.uniform(-50, 50)
        mutated.rating.economic += self._rng.uniform(-50, 50)
        mutated.rating.reasoning += self._rng.uniform(-30, 30)
        return mutated

    def crossover(self, parent_a: Agent, parent_b: Agent) -> Agent:
        child_type = self._rng.choice([parent_a.agent_type, parent_b.agent_type])
        if child_type == "trader":
            child = TraderAgent(name=f"cross_trader_gen{self.generation}")
        elif child_type == "crafter":
            child = CrafterAgent(name=f"cross_crafter_gen{self.generation}")
        elif child_type == "rl":
            child = RLAgent(name=f"cross_rl_gen{self.generation}")
        elif child_type == "meta":
            child = MetaStrategyAgent(name=f"cross_meta_gen{self.generation}")
        else:
            child = GW2EfficiencyToolAgent(name=f"cross_eff_gen{self.generation}")
        child.rating.skill = (parent_a.rating.skill + parent_b.rating.skill) / 2
        child.rating.economic = (parent_a.rating.economic + parent_b.rating.economic) / 2
        child.rating.reasoning = (parent_a.rating.reasoning + parent_b.rating.reasoning) / 2
        return child

    def evolve(self, population: list[Agent]) -> list[Agent]:
        self.generation += 1
        scores = self.evaluate(population)
        top_agents = self.select_top(scores, population)
        new_population: list[Agent] = []
        new_population.extend(copy.deepcopy(a) for a in top_agents)
        while len(new_population) < self.config.population_size:
            if self._rng.random() < self.config.crossover_rate and len(top_agents) >= 2:
                parent_a = self._rng.choice(top_agents)
                parent_b = self._rng.choice([a for a in top_agents if a.id != parent_a.id])
                child = self.crossover(parent_a, parent_b)
            else:
                parent = self._rng.choice(population)
                child = copy.deepcopy(parent)
                child.id = f"{parent.agent_type}:gen{self.generation}:{self._rng.randint(1000, 9999)}"
                child.name = f"{parent.name}_gen{self.generation}"
            if self._rng.random() < self.config.mutation_rate:
                child = self.mutate(child)
            new_population.append(child)
        new_population = new_population[:self.config.population_size]
        record = {
            "generation": self.generation,
            "population_size": len(new_population),
            "elite_count": len(top_agents),
            "avg_rating": round(sum(a.rating.overall for a in new_population) / len(new_population), 1) if new_population else 0,
            "top_rating": round(max(a.rating.overall for a in new_population), 1) if new_population else 0,
            "agent_types": {t: sum(1 for a in new_population if a.agent_type == t) for t in AGENT_TYPES},
        }
        self.history.append(record)
        return new_population
