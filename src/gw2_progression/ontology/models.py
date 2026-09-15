"""Ontology Pydantic models — the typed interfaces for the semantic layer."""

from pydantic import BaseModel


class OntologyObject(BaseModel):
    object_id: str
    class_name: str
    account_name: str = ""
    properties: dict = {}
    qa_status: str = "pending"
    privacy_scope: str = "private"
    revision: int = 1
    source_object_id: str = ""
    created_at: str = ""
    updated_at: str = ""


class OntologyRelation(BaseModel):
    relation_id: str
    source_id: str
    target_id: str
    relation_type: str
    properties: dict = {}
    confidence: float = 1.0
    created_at: str = ""


class OntologyAction(BaseModel):
    action_id: str
    action_type: str
    account_name: str = ""
    params: dict = {}
    preconditions_met: bool = False
    affected_object_ids: list[str] = []
    rollback_strategy: str = "manual"
    privacy_policy: str = "private"
    freshness_policy: str = "any"
    qa_status: str = "pending"
    status: str = "pending"
    error: str = ""
    created_at: str = ""
    completed_at: str = ""


class SafeSurplusResult(BaseModel):
    item_id: int
    item_name: str = ""
    total_owned: int = 0
    total_reserved: int = 0
    safe_surplus: int = 0
    reserved_by_goals: list[dict] = []
    evidence_source: str = ""
    qa_status: str = "pending"


class ImpactReport(BaseModel):
    item_id: int
    item_name: str = ""
    quantity_to_sell: int = 0
    risk_level: str = "low"
    affected_goals: list[dict] = []
    blocked_goals: list[str] = []
    partially_affected_goals: list[dict] = []
    warnings: list[str] = []
    safe_surplus: int = 0
    recommendation: str = ""
    evidence_source: str = ""
    qa_status: str = "pass"


class QAReport(BaseModel):
    target_object_id: str = ""
    target_class: str = ""
    checks: list[dict] = []
    passed: int = 0
    failed: int = 0
    blocking_errors: list[str] = []
    warnings: list[str] = []
    status: str = "pending"
    checked_at: str = ""


class ActionPlanResult(BaseModel):
    action_id: str = ""
    action_type: str = ""
    status: str = "pending"
    created_objects: list[str] = []
    created_relations: list[str] = []
    qa_report: QAReport | None = None
    error: str = ""
