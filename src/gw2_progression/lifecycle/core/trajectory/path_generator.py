from __future__ import annotations

from copy import deepcopy
from typing import Any

from gw2_progression.lifecycle.core.backward.inference_engine import BackwardInferenceEngine, InferredPath
from gw2_progression.lifecycle.core.forward.oosk_simulator import OOSKSimulator
from gw2_progression.lifecycle.core.validation.consistency_checker import ConsistencyChecker


class TrajectoryGenerator:
    def __init__(self, backward: BackwardInferenceEngine | None = None, forward: OOSKSimulator | None = None, validator: ConsistencyChecker | None = None) -> None:
        self.backward = backward or BackwardInferenceEngine()
        self.forward = forward or OOSKSimulator()
        self.validator = validator or ConsistencyChecker()

    def generate(self, current_state: dict[str, Any], max_depth: int = 10) -> list[InferredPath]:
        backward_paths = self.backward.infer_history(current_state, max_depth=max_depth)
        valid_paths: list[InferredPath] = []
        for path in backward_paths:
            if not path.steps:
                continue
            start_state = path.start_state or current_state
            forward_traj = self.forward.simulate(start_state, steps=len(path.steps))
            if forward_traj and self.validator.validate(forward_traj[-1] if forward_traj else {}, current_state):
                path.rule_consistency *= 1.1
                valid_paths.append(path)
            elif forward_traj:
                match_ratio = self.validator.match_ratio(forward_traj[-1] if forward_traj else {}, current_state)
                if match_ratio > 0.5:
                    path.rule_consistency *= match_ratio
                    valid_paths.append(path)
        return valid_paths

    def generate_from_hypotheses(self, current_state: dict[str, Any], hypotheses: list[dict[str, Any]]) -> list[InferredPath]:
        valid_paths: list[InferredPath] = []
        for hypothesis in hypotheses:
            steps = hypothesis.get("steps", [])
            if not steps:
                continue
            start_state = steps[0] if isinstance(steps[0], dict) and "market" in steps[0] else current_state
            forward_traj = self.forward.simulate_with_actions(start_state, steps)
            end_state = forward_traj[-1] if forward_traj else {}
            if self.validator.validate(end_state, current_state):
                path = InferredPath(
                    steps=steps,
                    probability=hypothesis.get("probability", 0.5),
                    start_state=start_state,
                    end_state=current_state,
                )
                valid_paths.append(path)
        return valid_paths

    def generate_counterfactual(self, current_state: dict[str, Any], altered_action: dict[str, Any], step_index: int = 0) -> list[InferredPath]:
        backward_paths = self.backward.infer_history(current_state, max_depth=10)
        counterfactuals: list[InferredPath] = []
        for path in backward_paths[:3]:
            if step_index < len(path.steps):
                altered_steps = deepcopy(path.steps)
                altered_steps[step_index] = altered_action
                alt_path = InferredPath(
                    steps=altered_steps,
                    probability=path.probability * 0.5,
                    rule_consistency=path.rule_consistency * 0.8,
                    start_state=path.start_state,
                    end_state=path.end_state,
                )
                counterfactuals.append(alt_path)
        return counterfactuals
