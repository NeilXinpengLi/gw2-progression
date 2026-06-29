"""REST API for the GW2 Rule Engine v1.

Exposes endpoints matching the spec:
  POST /rules/extract
  POST /rules/economy
  POST /rules/behavior
  POST /rules/distill
  POST /rules/validate
  POST /engine/run
"""

from __future__ import annotations

from fastapi import APIRouter, Body

from gw2_progression.expert_ai.core import expert_ai
from gw2_progression.rule_engine.core.api_rules.schema_parser import Rule
from gw2_progression.rule_engine.core.engine import GW2RuleEngine

router = APIRouter(prefix="/rules", tags=["rule-engine"])

_engine: GW2RuleEngine | None = None


def get_engine() -> GW2RuleEngine:
    global _engine
    if _engine is None:
        _engine = GW2RuleEngine(
            llm_layer=expert_ai.expert_layer if hasattr(expert_ai, "expert_layer") else None,
            simulation=expert_ai.simulation if hasattr(expert_ai, "simulation") else None,
        )
    return _engine


@router.post("/extract")
async def extract_api_rules():
    engine = get_engine()
    return engine.extract_api()


@router.post("/economy")
async def learn_economy_rules(body: dict = Body(default_factory=dict)):
    engine = get_engine()
    return engine.learn_economy(body.get("prices"))


@router.post("/behavior")
async def mine_behavior_rules(body: dict = Body(default_factory=dict)):
    engine = get_engine()
    return engine.mine_behavior(body.get("logs", []))


@router.post("/distill")
async def distill_rules(body: dict = Body(default_factory=dict)):
    engine = get_engine()
    raw = body.get("rules", [])
    rules = [Rule.from_dict(r) for r in raw] if raw else []
    return engine.distill(rules)


@router.post("/validate")
async def validate_rules(body: dict = Body(default_factory=dict)):
    engine = get_engine()
    raw = body.get("rules", [])
    rules = [Rule.from_dict(r) for r in raw]
    return engine.validate(rules, body.get("world", {}))


@router.post("/engine/run")
async def run_engine(body: dict = Body(default_factory=dict)):
    engine = get_engine()
    return engine.run(body)


@router.get("/status")
async def rule_engine_status():
    get_engine()
    return {"engine": "GW2 Rule Engine v1", "status": "ready"}
