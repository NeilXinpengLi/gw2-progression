from fastapi import APIRouter
from pydantic import BaseModel

from gw2_progression.rule_engine_v2.core.engine import get_rule_engine

router = APIRouter(prefix="/rules/v2", tags=["rule_engine_v2"])

_engine = get_rule_engine()


class ExtractRequest(BaseModel):
    rules: list[dict] | None = None


class SimulateRequest(BaseModel):
    steps: int = 10


class CompeteRequest(BaseModel):
    agent_count: int = 4


class EvolveRequest(BaseModel):
    population_size: int = 50


class DistillRequest(BaseModel):
    pass


class OptimizeRequest(BaseModel):
    pass


@router.post("/extract")
async def extract(body: ExtractRequest):
    rules = _engine.extract_rules(body.rules)
    return {"rules": rules, "count": len(rules)}


@router.post("/simulate")
async def simulate(body: SimulateRequest):
    return _engine.simulate_rules(steps=body.steps)


@router.post("/evolve")
async def evolve(body: EvolveRequest):
    rules = _engine.evolve_rules()
    return {
        "generation": _engine.evolution.generation,
        "population": len(rules),
        "history": _engine.evolution.history,
    }


@router.post("/compete")
async def compete(body: CompeteRequest):
    return _engine.compete_rules()


@router.post("/distill")
async def distill(body: DistillRequest):
    return {"distilled": _engine.distill_rules()}


@router.post("/optimize")
async def optimize(body: OptimizeRequest):
    return {"optimized": _engine.optimize_rules()}


@router.get("/leaderboard")
async def leaderboard():
    return _engine.tournament.ranking.leaderboard(_engine.agents)


@router.post("/pipeline")
async def pipeline():
    return _engine.run_full_pipeline()
