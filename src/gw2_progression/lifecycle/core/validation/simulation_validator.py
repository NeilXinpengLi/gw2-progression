from __future__ import annotations

from typing import Any

from gw2_progression.lifecycle.core.backward.inference_engine import InferredPath
from gw2_progression.lifecycle.core.forward.oosk_simulator import OOSKSimulator
from gw2_progression.lifecycle.core.rules.dgsk_constraints import DGSKConstraints
from gw2_progression.lifecycle.core.validation.consistency_checker import ConsistencyChecker


class SimulationValidator:
    def __init__(self, forward: OOSKSimulator | None = None, constraints: DGSKConstraints | None = None, consistency: ConsistencyChecker | None = None) -> None:
        self.forward = forward or OOSKSimulator()
        self.constraints = constraints or DGSKConstraints()
        self.consistency = consistency or ConsistencyChecker()

    def validate_path(self, path: InferredPath, final_state: dict[str, Any]) -> dict[str, Any]:
        if not path.steps:
            return {"valid": False, "reason": "Empty path"}
        trajectory = self.forward.simulate_with_actions(path.start_state, path.steps)
        valid_steps = 0
        total_steps = len(trajectory)
        for state in trajectory:
            if self.constraints.validate(state):
                valid_steps += 1
        constraint_pass = valid_steps / max(total_steps, 1)
        consistency_score = self.consistency.validate_trajectory(trajectory, final_state)
        deviation = 1.0 - consistency_score
        valid = constraint_pass >= 0.5 and deviation <= self.consistency.tolerance
        return {
            "valid": valid,
            "valid_steps": valid_steps,
            "total_steps": total_steps,
            "constraint_compliance": round(constraint_pass, 4),
            "consistency_score": round(consistency_score, 4),
            "deviation": round(deviation, 4),
        }

    def validate_state(self, state: dict[str, Any]) -> dict[str, Any]:
        return self.constraints.validate_detailed(state)

    def simulate_and_validate(self, state: dict[str, Any], steps: int = 10, goal_state: dict[str, Any] | None = None) -> dict[str, Any]:
        trajectory = self.forward.simulate(state, steps=steps)
        validation_steps: list[dict[str, Any]] = []
        for t, s in enumerate(trajectory):
            v = self.constraints.validate_detailed(s)
            validation_steps.append({
                "step": t,
                "valid": v["valid"],
                "details": v,
            })
        result = {
            "trajectory_length": len(trajectory),
            "steps": validation_steps,
            "all_valid": all(v["valid"] for v in validation_steps),
        }
        if goal_state:
            end_state = trajectory[-1] if trajectory else {}
            result["goal_match"] = self.consistency.match_ratio(end_state, goal_state)
        return result
