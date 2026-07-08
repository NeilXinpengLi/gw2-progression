"""Foundry-grade Ontology Execution OS facade.

This module makes the convergence rule explicit: plugins may propose ontology
actions, but only OntologyKernel may mutate state.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol

from gw2_progression.ontology.runtime_kernel import OntologyKernel


class KernelPluginRole(StrEnum):
    DATA_INGESTION = "data_ingestion"
    AI_SUGGESTION = "ai_suggestion"
    RULE_VALIDATION = "rule_validation"
    SIMULATION = "simulation"
    COMMERCE = "commerce"
    ANALYTICS = "analytics"


class KernelMutationPolicy(StrEnum):
    PROPOSE_ONLY = "propose_only"
    KERNEL_EXECUTE_ONLY = "kernel_execute_only"


@dataclass(frozen=True)
class KernelActionProposal:
    plugin_id: str
    role: KernelPluginRole
    action: dict[str, Any]
    evidence: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    mutation_policy: KernelMutationPolicy = KernelMutationPolicy.PROPOSE_ONLY

    def to_dict(self) -> dict[str, Any]:
        return {
            "plugin_id": self.plugin_id,
            "role": self.role.value,
            "action": copy.deepcopy(self.action),
            "evidence": copy.deepcopy(self.evidence),
            "confidence": self.confidence,
            "mutation_policy": self.mutation_policy.value,
        }


class KernelPlugin(Protocol):
    plugin_id: str
    role: KernelPluginRole

    def propose(self, payload: dict[str, Any]) -> list[KernelActionProposal]:
        ...


class KernelMutationGuard:
    """Rejects plugin outputs that try to bypass the kernel mutation path."""

    MUTATING_KEYS = {"state", "entities", "relations", "lineage", "state_hash"}

    def validate_proposal(self, proposal: KernelActionProposal) -> dict[str, Any]:
        errors: list[str] = []
        if proposal.mutation_policy != KernelMutationPolicy.PROPOSE_ONLY:
            errors.append("plugin:mutation_policy_must_be_propose_only")
        action = proposal.action
        if not isinstance(action, dict):
            errors.append("plugin:action_must_be_dict")
        elif not (action.get("type") or action.get("action_type")):
            errors.append("plugin:action_type_required")
        for key in self.MUTATING_KEYS:
            if key in proposal.evidence:
                errors.append(f"plugin:evidence_must_not_include_mutating_key:{key}")
        return {"valid": not errors, "errors": errors, "proposal": proposal.to_dict()}


class OntologyExecutionOS:
    """Single-kernel execution facade for Data Mesh, AI, Rule, Lifecycle, and Commerce plugins."""

    def __init__(self, kernel: OntologyKernel | None = None, tenant_id: str = "default") -> None:
        self.kernel = kernel or OntologyKernel(tenant_id=tenant_id, load_persisted=True)
        self.guard = KernelMutationGuard()

    def propose(self, plugin: KernelPlugin, payload: dict[str, Any]) -> dict[str, Any]:
        proposals = plugin.propose(payload)
        validations = [self.guard.validate_proposal(proposal) for proposal in proposals]
        return {
            "status": "accepted" if all(item["valid"] for item in validations) else "rejected",
            "plugin_id": plugin.plugin_id,
            "role": plugin.role.value,
            "proposal_count": len(proposals),
            "validations": validations,
        }

    def execute_proposals(self, proposals: list[KernelActionProposal]) -> dict[str, Any]:
        executions: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        for proposal in proposals:
            validation = self.guard.validate_proposal(proposal)
            if not validation["valid"]:
                rejected.append(validation)
                continue
            executions.append(self.kernel.execute_kernel_action(proposal.action, source=proposal.plugin_id))
        return {
            "kernel": "OntologyKernel",
            "single_execution_truth": True,
            "executed_count": len(executions),
            "rejected_count": len(rejected),
            "executions": executions,
            "rejected": rejected,
            "state_hash": self.kernel.snapshot()["state_hash"],
            "lineage_count": len(self.kernel.snapshot()["lineage"]),
        }

    def execute_plugin(self, plugin: KernelPlugin, payload: dict[str, Any]) -> dict[str, Any]:
        proposals = plugin.propose(payload)
        result = self.execute_proposals(proposals)
        return {**result, "plugin_id": plugin.plugin_id, "role": plugin.role.value}


class AISuggestionPlugin:
    plugin_id = "ai_lab:suggestion_plugin"
    role = KernelPluginRole.AI_SUGGESTION

    def propose(self, payload: dict[str, Any]) -> list[KernelActionProposal]:
        decision = {
            "decision": str(payload.get("decision") or payload.get("action") or "REVIEW"),
            "score": float(payload.get("score", payload.get("confidence", 0.5)) or 0.5),
            "source": self.plugin_id,
            "reason": str(payload.get("reason", "")),
        }
        return [
            KernelActionProposal(
                plugin_id=self.plugin_id,
                role=self.role,
                action={"type": "record_decision", "decision": decision},
                evidence={"payload": copy.deepcopy(payload), "mode": "proposal_only"},
                confidence=decision["score"],
            )
        ]


class RuleValidationPlugin:
    plugin_id = "rule_engine_v2:validation_plugin"
    role = KernelPluginRole.RULE_VALIDATION

    def propose(self, payload: dict[str, Any]) -> list[KernelActionProposal]:
        score = 1.0 if payload.get("valid", True) else 0.0
        decision = {
            "decision": "RULE_VALIDATION_PASS" if score else "RULE_VALIDATION_BLOCK",
            "score": score,
            "source": self.plugin_id,
        }
        return [
            KernelActionProposal(
                plugin_id=self.plugin_id,
                role=self.role,
                action={"type": "record_decision", "decision": decision},
                evidence={"warnings": list(payload.get("warnings", [])), "mode": "validation_evidence"},
                confidence=score,
            )
        ]


class CommerceLineagePlugin:
    plugin_id = "commerce:lineage_plugin"
    role = KernelPluginRole.COMMERCE

    def propose(self, payload: dict[str, Any]) -> list[KernelActionProposal]:
        decision = {
            "decision": str(payload.get("event_type", "COMMERCE_EVENT")),
            "score": 1.0,
            "source": self.plugin_id,
            "order_id": str(payload.get("order_id", "")),
        }
        return [
            KernelActionProposal(
                plugin_id=self.plugin_id,
                role=self.role,
                action={"type": "record_decision", "decision": decision},
                evidence={"idempotency_key": payload.get("idempotency_key", ""), "mode": "commerce_lineage"},
                confidence=1.0,
            )
        ]
