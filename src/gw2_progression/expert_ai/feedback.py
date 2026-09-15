"""Memory feedback loop for Expert AI decisions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from gw2_progression.expert_ai.core import ExpertRuntime, MemorySystem


class MemoryFeedbackLoop:
    """Observe runtime outcomes and update memory-derived reasoning weights."""

    def __init__(self, runtime: ExpertRuntime, memory: MemorySystem) -> None:
        self.runtime = runtime
        self.memory = memory
        self.reasoning_weights: dict[str, float] = {
            "approve_success": 1.0,
            "reject_success": 1.0,
            "review_success": 1.0,
            "risk_penalty": 1.0,
        }

    def observe(self, event: dict[str, Any]) -> dict[str, Any]:
        record = self.memory.append({"type": "feedback", **event})
        evaluation = self.evaluate_outcome(record)
        patterns = self.memory.update_patterns()
        weights = self.adjust_reasoning_weights(evaluation)
        return {"event": record, "evaluation": evaluation, "patterns": patterns, "reasoning_weights": weights}

    def evaluate_outcome(self, event: dict[str, Any]) -> dict[str, Any]:
        decision = str(event.get("decision", "REVIEW")).upper()
        outcome = str(event.get("outcome", "unknown")).lower()
        success = outcome in {"success", "accepted", "completed", "profitable", "ready"}
        risk = float(event.get("risk", 0) or 0)
        signal = f"{decision.lower()}_{'success' if success else 'failure'}"
        return {"decision": decision, "outcome": outcome, "success": success, "risk": risk, "signal": signal}

    def adjust_reasoning_weights(self, evaluation: dict[str, Any]) -> dict[str, float]:
        decision = evaluation["decision"].lower()
        if evaluation["success"]:
            key = f"{decision}_success"
            self.reasoning_weights[key] = round(self.reasoning_weights.get(key, 1.0) + 0.05, 3)
        else:
            self.reasoning_weights["risk_penalty"] = round(self.reasoning_weights["risk_penalty"] + max(evaluation["risk"], 0.05), 3)
        return dict(self.reasoning_weights)

    def status(self) -> dict[str, Any]:
        return {
            "event_count": len(self.memory.events),
            "snapshot_count": len(self.runtime.snapshots),
            "reasoning_weights": dict(self.reasoning_weights),
        }
