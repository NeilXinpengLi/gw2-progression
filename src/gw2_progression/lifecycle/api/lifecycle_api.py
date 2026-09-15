from fastapi import APIRouter
from pydantic import BaseModel

from gw2_progression.lifecycle.core.engine import get_lifecycle

router = APIRouter(prefix="/lifecycle", tags=["lifecycle"])

_engine = get_lifecycle()


class ReconstructRequest(BaseModel):
    state: dict
    max_depth: int = 10


class ReconstructItemRequest(BaseModel):
    item_id: str
    state: dict


class SimulateRequest(BaseModel):
    state: dict
    steps: int = 10


class ValidateRequest(BaseModel):
    state: dict


class CraftingCheckRequest(BaseModel):
    inventory: dict[str, int]
    recipe_id: str


class CraftingChainRequest(BaseModel):
    target_item: str
    inventory: dict[str, int] | None = None


class EconomyCheckRequest(BaseModel):
    market: dict[str, dict]


class CounterfactualRequest(BaseModel):
    state: dict
    altered_action: dict
    step_index: int = 0


@router.post("/reconstruct")
async def reconstruct(body: ReconstructRequest):
    return _engine.reconstruct(body.state, max_depth=body.max_depth)


@router.post("/reconstruct/item")
async def reconstruct_item(body: ReconstructItemRequest):
    return _engine.reconstruct_item(body.item_id, body.state)


@router.post("/simulate")
async def simulate(body: SimulateRequest):
    return _engine.simulate_forward(body.state, steps=body.steps)


@router.post("/validate")
async def validate(body: ValidateRequest):
    return _engine.validate_state(body.state)


@router.post("/crafting/check")
async def crafting_check(body: CraftingCheckRequest):
    return _engine.check_crafting(body.inventory, body.recipe_id)


@router.post("/crafting/chain")
async def crafting_chain(body: CraftingChainRequest):
    return _engine.get_crafting_chain(body.target_item, body.inventory)


@router.post("/economy/check")
async def economy_check(body: EconomyCheckRequest):
    return _engine.check_economy(body.market)


@router.post("/counterfactual")
async def counterfactual(body: CounterfactualRequest):
    return _engine.counterfactual(body.state, body.altered_action, step_index=body.step_index)


@router.post("/report")
async def report(body: ValidateRequest):
    return _engine.generate_report(body.state)
