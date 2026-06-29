from __future__ import annotations

import random
from typing import Any

from gw2_progression.rule_engine_v2.core.evolution.rule_mutator import RuleMutator
from gw2_progression.rule_engine_v2.core.evolution.rule_selector import RuleSelector
from gw2_progression.rule_engine_v2.core.rl.reward_engine import RuleReward


class RuleEvolutionSystem:
    def __init__(self, population_size: int = 50, mutation_rate: float = 0.3, elite_ratio: float = 0.3) -> None:
        self.population_size = population_size
        self.mutator = RuleMutator(mutation_rate=mutation_rate)
        self.selector = RuleSelector(elite_ratio=elite_ratio)
        self.reward = RuleReward()
        self._rng = random.Random(1)
        self.generation = 0
        self.history: list[dict[str, Any]] = []

    def evolve(self, rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
        self.generation += 1
        if not rules:
            return self._seed_population()
        elite = self.selector.select_elite(rules, self.reward)
        offspring: list[dict[str, Any]] = []
        while len(elite) + len(offspring) < self.population_size:
            parent = self.selector.tournament_select(rules, self.reward)
            child = self.mutator.mutate(parent)
            child["id"] = f"evolved:gen{self.generation}:{self._rng.randint(10000, 99999)}"
            child["generation"] = self.generation
            offspring.append(child)
        new_population = elite + offspring[:self.population_size - len(elite)]
        self._record_generation(new_population)
        return new_population

    def select(self, rules: list[dict[str, Any]], k: int = 10) -> list[dict[str, Any]]:
        scored = [(r, self.reward.fitness(r)) for r in rules]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [r for r, _ in scored[:k]]

    def _seed_population(self) -> list[dict[str, Any]]:
        population: list[dict[str, Any]] = []
        types = ["crafting", "economy", "behavior", "meta"]
        for i in range(self.population_size):
            rtype = types[i % len(types)]
            rule = {
                "id": f"seed:gen{self.generation}:{i}",
                "type": rtype,
                "name": f"Seed {rtype} rule {i}",
                "action": self._rng.choice(["trade", "craft", "farm", "collect"]),
                "target": "market",
                "price_impact": self._rng.uniform(-0.05, 0.05),
                "base_accuracy": self._rng.uniform(0.3, 0.9),
                "profit": self._rng.uniform(0, 50),
                "volatility": self._rng.uniform(0, 0.5),
                "priority": self._rng.randint(1, 5),
                "active": True,
                "generation": self.generation,
                "conditions": [],
                "actions": [],
            }
            population.append(rule)
        return population

    def _record_generation(self, population: list[dict[str, Any]]) -> None:
        fitnesses = [self.reward.fitness(r) for r in population]
        self.history.append({
            "generation": self.generation,
            "population_size": len(population),
            "avg_fitness": round(sum(fitnesses) / max(len(fitnesses), 1), 4),
            "max_fitness": round(max(fitnesses), 4),
            "min_fitness": round(min(fitnesses), 4),
            "types": {t: sum(1 for r in population if r.get("type") == t) for t in ["crafting", "economy", "behavior", "meta"]},
        })
