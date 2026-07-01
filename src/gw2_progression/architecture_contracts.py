"""Architecture convergence contracts for product safety and AI Lab isolation."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any

from gw2_progression.api.governance import API_ROUTE_GOVERNANCE, ApiCategory

PRODUCT_PLAN_OWNER = "gw2_progression.services.goal_driven_engine.generate_plan_from_goal"
PRODUCT_DECISION_FACADE = "Goal-Driven OS"
EVIDENCE_SPINE = "Ontology Runtime"
DATA_GOVERNANCE_OWNER = "Data Mesh"
OFFLINE_LEARNING_OWNER = "Expert AI"

EXPERIMENTAL_DECISION_MODULES = {
    "gw2_progression.services.production_engine",
    "gw2_progression.services.v4_optimizer",
    "gw2_progression.services.v5_learning",
    "gw2_progression.expert_ai",
    "gw2_progression.cognitive_os",
    "gw2_progression.benchmark",
    "gw2_progression.rule_engine_v2",
    "gw2_progression.lifecycle",
}


@dataclass(frozen=True)
class EvidenceEnvelope:
    evidence_type: str
    producer: str
    subject_id: str
    payload: dict[str, Any]
    source_refs: list[str] = field(default_factory=list)
    schema_version: str = "evidence.v1"
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        content = {
            "schema_version": self.schema_version,
            "evidence_type": self.evidence_type,
            "producer": self.producer,
            "subject_id": self.subject_id,
            "payload": self.payload,
            "source_refs": list(self.source_refs),
            "created_at": self.created_at,
        }
        content["content_hash"] = stable_hash({k: v for k, v in content.items() if k != "content_hash"})
        return content


@dataclass(frozen=True)
class PlanOutcomeEvent:
    plan_id: str
    action_id: str
    action_type: str
    account_hash: str
    goal_type: str
    confidence: float
    data_sources: list[str]
    outcome: dict[str, Any]
    schema_version: str = "plan_action_outcome.v1"
    created_at: float = field(default_factory=time.time)

    def to_training_event(self) -> dict[str, Any]:
        reward = float(self.outcome.get("reward", self.outcome.get("value_delta", 0)) or 0)
        success = bool(self.outcome.get("success", reward > 0))
        return {
            "id": stable_hash({"plan_id": self.plan_id, "action_id": self.action_id, "account_hash": self.account_hash})[:16],
            "schema_version": self.schema_version,
            "state": {
                "goal_type": self.goal_type,
                "confidence": self.confidence,
                "source_count": len(self.data_sources),
            },
            "decision": {
                "type": self.action_type,
                "plan_id": self.plan_id,
                "action_id": self.action_id,
                "data_sources": list(self.data_sources),
            },
            "outcome": {**self.outcome, "success": success, "reward": reward},
            "agent_type": "goal_driven_plan_adapter",
            "timestamp": self.created_at,
        }


def stable_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")).hexdigest()


def validate_evidence_envelope(envelope: dict[str, Any]) -> dict[str, Any]:
    required = {"schema_version", "evidence_type", "producer", "subject_id", "payload", "source_refs", "created_at", "content_hash"}
    missing = sorted(required - set(envelope))
    expected_hash = stable_hash({k: v for k, v in envelope.items() if k != "content_hash"}) if not missing else ""
    valid_hash = bool(expected_hash and envelope.get("content_hash") == expected_hash)
    return {"valid": not missing and valid_hash, "missing": missing, "valid_hash": valid_hash, "expected_hash": expected_hash}


def anonymize_account(account_name: str) -> str:
    return stable_hash({"account_name": account_name})[:16]


def decision_owner_contract() -> dict[str, Any]:
    ai_lab_routes = [key for key, meta in API_ROUTE_GOVERNANCE.items() if meta.category == ApiCategory.AI_LAB]
    return {
        "product_plan_owner": PRODUCT_PLAN_OWNER,
        "product_decision_facade": PRODUCT_DECISION_FACADE,
        "evidence_spine": EVIDENCE_SPINE,
        "data_governance_owner": DATA_GOVERNANCE_OWNER,
        "offline_learning_owner": OFFLINE_LEARNING_OWNER,
        "experimental_decision_modules": sorted(EXPERIMENTAL_DECISION_MODULES),
        "ai_lab_route_keys": sorted(ai_lab_routes),
    }


def data_source_governance_contract() -> dict[str, Any]:
    return {
        "source_identity_owner": DATA_GOVERNANCE_OWNER,
        "source_confidence_owner": DATA_GOVERNANCE_OWNER,
        "fetch_pipeline_owner": "Data Acquisition",
        "product_consumption_rule": "Core Product consumes snapshots plus Data Mesh confidence, not raw source trust logic.",
        "canonical_registry": "gw2_progression.data_mesh.sources.registry.SourceRegistry",
        "pipeline_registry": "gw2_progression.data_acquisition.registry.source_registry.SourceRegistry",
    }


def data_source_governance_snapshot() -> dict[str, Any]:
    from gw2_progression.data_acquisition.registry.source_registry import SourceRegistry as AcquisitionSourceRegistry
    from gw2_progression.data_mesh.sources.registry import BUILTIN_SOURCES
    from gw2_progression.data_mesh.sources.registry import SourceRegistry as MeshSourceRegistry

    mesh = MeshSourceRegistry()
    for source in BUILTIN_SOURCES:
        mesh.register(source)
    acquisition = AcquisitionSourceRegistry()
    mesh_sources = mesh.to_dict().get("sources", {})
    acquisition_sources = acquisition.to_dict().get("sources", [])
    return {
        "contract": data_source_governance_contract(),
        "mesh_source_count": len(mesh_sources),
        "acquisition_source_count": len(acquisition_sources),
        "source_confidence_owner": DATA_GOVERNANCE_OWNER,
        "fetch_pipeline_owner": "Data Acquisition",
        "mesh_source_ids": sorted(mesh_sources)[:25],
        "acquisition_source_ids": sorted(source.get("id", "") for source in acquisition_sources)[:25],
    }
