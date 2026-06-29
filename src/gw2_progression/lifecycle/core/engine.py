from __future__ import annotations

from typing import Any

from gw2_progression.lifecycle.core.backward.dependency_solver import DependencySolver
from gw2_progression.lifecycle.core.backward.inference_engine import BackwardInferenceEngine, InferredPath
from gw2_progression.lifecycle.core.forward.oosk_simulator import OOSKSimulator
from gw2_progression.lifecycle.core.forward.state_evolver import StateEvolver
from gw2_progression.lifecycle.core.rules.crafting_rules import CraftingRules
from gw2_progression.lifecycle.core.rules.dgsk_constraints import DGSKConstraints
from gw2_progression.lifecycle.core.rules.economy_rules import EconomyRules
from gw2_progression.lifecycle.core.trajectory.path_generator import TrajectoryGenerator
from gw2_progression.lifecycle.core.trajectory.path_ranker import PathRanker
from gw2_progression.lifecycle.core.validation.consistency_checker import ConsistencyChecker
from gw2_progression.lifecycle.core.validation.simulation_validator import SimulationValidator


class LifecycleEngine:
    def __init__(self) -> None:
        self.solver = DependencySolver()
        self.solver.register_account_dependencies()
        self.evolver = StateEvolver(solver=self.solver)
        self.backward = BackwardInferenceEngine()
        self.forward = OOSKSimulator(evolver=self.evolver)
        self.constraints = DGSKConstraints()
        self.crafting = CraftingRules()
        self.economy = EconomyRules()
        self.validator = ConsistencyChecker()
        self.sim_validator = SimulationValidator()
        self.path_generator = TrajectoryGenerator(
            backward=self.backward,
            forward=self.forward,
            validator=self.validator,
        )
        self.ranker = PathRanker()

    def reconstruct(self, current_state: dict[str, Any], max_depth: int = 10) -> dict[str, Any]:
        candidates = self.backward.infer_history(current_state, max_depth=max_depth)
        trajectories: list[InferredPath] = []
        for c in candidates:
            if c.steps:
                c.end_state = dict(current_state)
                traj = self.forward.simulate_with_actions(dict(current_state), c.steps)
                if traj:
                    end_state = traj[-1]
                    c.validations = end_state.get("_action_validations", [])
                    c.validation_summary = self.evolver.validation_summary(end_state)
                    if self.validator.validate(end_state, current_state):
                        c.rule_consistency *= 1.1
                        trajectories.append(c)
                    else:
                        ratio = self.validator.match_ratio(end_state, current_state)
                        if ratio > 0.5:
                            c.rule_consistency *= ratio
                            trajectories.append(c)
        ranked = self.ranker.rank(trajectories)
        return self._build_reconstruction_output(ranked, current_state)

    def reconstruct_item(self, item_id: str, current_state: dict[str, Any]) -> dict[str, Any]:
        from gw2_progression.lifecycle.core.backward.hypothesis_generator import HypothesisGenerator
        hg = HypothesisGenerator()
        hypotheses = hg.generate_for_item(item_id, current_state)
        paths = self.path_generator.generate_from_hypotheses(current_state, [h.__dict__ for h in hypotheses])
        ranked = self.ranker.rank(paths)
        return self._build_reconstruction_output(ranked, current_state, item_id=item_id)

    def simulate_forward(self, state: dict[str, Any], steps: int = 10) -> dict[str, Any]:
        trajectory = self.forward.simulate(state, steps=steps)
        return {
            "trajectory": trajectory,
            "length": len(trajectory),
            "end_state": trajectory[-1] if trajectory else state,
            "validation": self.constraints.validate_detailed(trajectory[-1]) if trajectory else {},
            "action_validations": self.evolver.validation_summary(trajectory[-1]) if trajectory else {},
        }

    def validate_state(self, state: dict[str, Any]) -> dict[str, Any]:
        return self.constraints.validate_detailed(state)

    def check_crafting(self, inventory: dict[str, int], recipe_id: str) -> dict[str, Any]:
        return self.crafting.craft(dict(inventory), recipe_id)

    def get_crafting_chain(self, target_item: str, inventory: dict[str, int] | None = None) -> list[dict[str, Any]]:
        return self.crafting.get_crafting_chain(target_item, inventory)

    def check_economy(self, market: dict[str, Any]) -> dict[str, Any]:
        return self.economy.validate_economy_state({"market": market})

    def counterfactual(self, current_state: dict[str, Any], altered_action: dict[str, Any], step_index: int = 0) -> dict[str, Any]:
        paths = self.path_generator.generate_counterfactual(current_state, altered_action, step_index)
        ranked = self.ranker.rank(paths)
        return self._build_reconstruction_output(ranked, current_state, counterfactual=True)

    def generate_report(self, current_state: dict[str, Any]) -> dict[str, Any]:
        reconstruction = self.reconstruct(current_state)
        validation = self.validate_state(current_state)
        return {
            "lifecycle_summary": reconstruction,
            "state_validation": validation,
            "trajectory_count": len(reconstruction.get("paths", [])),
            "most_likely_path": reconstruction.get("paths", [])[0] if reconstruction.get("paths") else None,
        }

    def _build_reconstruction_output(self, ranked_paths: list[InferredPath], current_state: dict[str, Any], item_id: str | None = None, counterfactual: bool = False) -> dict[str, Any]:
        return {
            "type": "counterfactual" if counterfactual else "reconstruction",
            "item_id": item_id,
            "state_snapshot": {
                "inventory": current_state.get("inventory", {}),
                "market": current_state.get("market", {}),
                "achievements": current_state.get("achievements", []),
            },
            "paths": [
                {
                    "rank": idx + 1,
                    "score": round(self.ranker._score(p), 4) if ranked_paths else 0,
                    "steps": p.steps,
                    "probability": p.probability,
                    "rule_consistency": p.rule_consistency,
                    "economy_likelihood": p.economy_likelihood,
                    "step_count": len(p.steps),
                    "step_types": list(set(s.get("type", "") for s in p.steps)) if p.steps else [],
                    "validations": p.validations,
                    "validation_summary": p.validation_summary,
                }
                for idx, p in enumerate(ranked_paths)
            ],
            "total_paths": len(ranked_paths),
            "timestamp": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        }


_lifecycle: LifecycleEngine | None = None


def get_lifecycle() -> LifecycleEngine:
    global _lifecycle
    if _lifecycle is None:
        _lifecycle = LifecycleEngine()
    return _lifecycle
