from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from gw2_progression.lifecycle.core.backward.hypothesis_generator import HypothesisGenerator
from gw2_progression.lifecycle.core.rules.dgsk_constraints import DGSKConstraints


@dataclass
class InferredPath:
    steps: list[dict[str, Any]]
    probability: float = 1.0
    rule_consistency: float = 1.0
    economy_likelihood: float = 1.0
    start_state: dict[str, Any] = field(default_factory=dict)
    end_state: dict[str, Any] = field(default_factory=dict)
    hypotheses: list[dict[str, Any]] = field(default_factory=list)
    validations: list[dict[str, Any]] = field(default_factory=list)
    validation_summary: dict[str, Any] = field(default_factory=dict)

    def copy(self) -> InferredPath:
        return InferredPath(
            steps=list(self.steps),
            probability=self.probability,
            rule_consistency=self.rule_consistency,
            economy_likelihood=self.economy_likelihood,
            start_state=dict(self.start_state),
            end_state=dict(self.end_state),
            hypotheses=list(self.hypotheses),
        )


class BackwardInferenceEngine:
    def __init__(self, constraints: DGSKConstraints | None = None, hypothesis_generator: HypothesisGenerator | None = None) -> None:
        self.constraints = constraints or DGSKConstraints()
        self.hypothesis_generator = hypothesis_generator or HypothesisGenerator()

    def infer_history(self, current_state: dict[str, Any], max_depth: int = 10) -> list[InferredPath]:
        hypotheses = self.hypothesis_generator.generate(current_state, max_depth=max_depth)
        paths: list[InferredPath] = []
        for hypothesis in hypotheses:
            path = self._apply_reverse_rules(hypothesis, current_state)
            if path:
                paths.append(path)
        return self._rank(paths)

    def infer_history_with_rules(self, current_state: dict[str, Any], rules: list[Any], max_depth: int = 10) -> list[InferredPath]:
        paths: list[InferredPath] = []
        for rule in rules:
            path = self.apply_reverse_rule(rule, current_state)
            if path:
                paths.append(path)
        return self._rank(paths)

    def apply_reverse_rule(self, rule: Any, state: dict[str, Any]) -> InferredPath | None:
        try:
            if hasattr(rule, "reverse_apply"):
                result = rule.reverse_apply(state)
                if result:
                    steps = result.get("steps", [])
                    return InferredPath(
                        steps=steps,
                        probability=result.get("probability", 0.5),
                        rule_consistency=result.get("rule_consistency", 0.8),
                        start_state=result.get("start_state", state),
                        end_state=state,
                    )
            return None
        except Exception:
            return None

    def _apply_reverse_rules(self, hypothesis: Any, current_state: dict[str, Any]) -> InferredPath | None:
        if hasattr(hypothesis, "steps"):
            steps = hypothesis.steps
            probability = getattr(hypothesis, "probability", 0.5)
            economy_likelihood = getattr(hypothesis, "economy_likelihood", 0.5)
        elif isinstance(hypothesis, dict):
            steps = hypothesis.get("steps", [])
            probability = hypothesis.get("probability", 0.5)
            economy_likelihood = hypothesis.get("economy_likelihood", 0.5)
        else:
            return None
        if not steps:
            return None
        start_state = steps[0] if steps else current_state
        rule_pass = sum(1 for s in steps if self.constraints.validate(s)) / max(len(steps), 1)
        return InferredPath(
            steps=steps,
            probability=probability,
            rule_consistency=rule_pass,
            economy_likelihood=economy_likelihood,
            start_state=start_state,
            end_state=current_state,
            hypotheses=[hypothesis] if not isinstance(hypothesis, list) else hypothesis,
        )

    def _rank(self, paths: list[InferredPath]) -> list[InferredPath]:
        return sorted(
            paths,
            key=lambda p: p.probability * p.rule_consistency * p.economy_likelihood,
            reverse=True,
        )
