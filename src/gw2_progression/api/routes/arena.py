from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from gw2_progression.benchmark.arena import get_arena

router = APIRouter(prefix="/arena", tags=["arena"])

_arena = get_arena()


class RunMatchRequest(BaseModel):
    agent_ids: list[str] | None = None
    max_steps: int = 50


class SimulateRequest(BaseModel):
    ticks: int = 50
    agent_ids: list[str] | None = None


class EvolveRequest(BaseModel):
    generations: int = 3


class EconomyUpdateRequest(BaseModel):
    items: dict[str, dict[str, float]]


class EloUpdateRequest(BaseModel):
    agent_id: str
    profit: float = 0.0
    efficiency: float = 0.0
    reasoning: float = 0.0
    stability: float = 0.0


class TournamentRequest(BaseModel):
    agent_ids: list[str] | None = None
    max_steps: int = 50
    rounds: int = 1


@router.post("/run_match")
async def run_match(body: RunMatchRequest):
    return _arena.run_match(agent_ids=body.agent_ids, max_steps=body.max_steps)


@router.post("/simulate")
async def simulate(body: SimulateRequest):
    return _arena.run_simulation(ticks=body.ticks, agent_ids=body.agent_ids)


@router.post("/agent/evolve")
async def evolve(body: EvolveRequest):
    return _arena.run_evolution(generations=body.generations)


@router.post("/economy/update")
async def economy_update(body: EconomyUpdateRequest):
    return _arena.economy_update(body.items)


@router.post("/elo/update")
async def elo_update(body: EloUpdateRequest):
    result = {
        "profit": body.profit,
        "efficiency": body.efficiency,
        "reasoning": body.reasoning,
        "stability": body.stability,
    }
    return _arena.update_elo(body.agent_id, result)


@router.get("/leaderboard")
async def leaderboard(sort_by: str = Query("overall", description="overall, skill, economic, reasoning, wins")):
    return _arena.get_leaderboard(sort_by=sort_by)


@router.post("/tournament")
async def tournament(body: TournamentRequest):
    return _arena.run_tournament(agent_ids=body.agent_ids, max_steps=body.max_steps, rounds=body.rounds)
