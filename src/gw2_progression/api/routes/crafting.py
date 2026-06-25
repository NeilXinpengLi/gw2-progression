import re
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from gw2_progression.gw2_client import Gw2ApiError
from gw2_progression.models import CraftingPlanResult, CraftingResponse, RecipeOptimizationResult
from gw2_progression.services.crafting_plan_service import create_plan
from gw2_progression.services.recipe_optimizer import optimize
from gw2_progression.services.recipe_service import calculate, calculate_cheapest
from gw2_progression.services.static_data_service import (
    find_recipes_by_output,
    get_ingest_progress,
    refresh_items,
    refresh_recipes,
)

STRATEGIES = ["cheapest", "fastest", "use_owned_first", "preserve_owned", "minimize_gold"]

router = APIRouter(prefix="/crafting", tags=["crafting"])

_KEY_PATTERN = re.compile(r"^[0-9A-Fa-f-]+$")


class OptimizeRequest(BaseModel):
    api_key: str
    target_item_id: int
    target_count: int = 1
    strategy: str = "cheapest"
    use_owned: bool = True

    @field_validator("api_key")
    @classmethod
    def opt_key_valid(cls, v: str) -> str:
        stripped = v.strip()
        if len(stripped) < 8:
            raise ValueError("API key must be at least 8 characters")
        if not _KEY_PATTERN.match(stripped):
            raise ValueError("API key contains invalid characters (expected hex + dashes)")
        return stripped

    @field_validator("strategy")
    @classmethod
    def strategy_valid(cls, v: str) -> str:
        if v not in STRATEGIES:
            raise ValueError(f"Strategy must be one of: {', '.join(STRATEGIES)}")
        return v


class CraftCalcRequest(BaseModel):
    api_key: str
    target_item_id: int
    quantity: int = 1
    use_owned: bool = True

    @field_validator("api_key")
    @classmethod
    def cc_key_valid(cls, v: str) -> str:
        stripped = v.strip()
        if len(stripped) < 8:
            raise ValueError("API key must be at least 8 characters")
        if not _KEY_PATTERN.match(stripped):
            raise ValueError("API key contains invalid characters (expected hex + dashes)")
        return stripped

    @field_validator("quantity")
    @classmethod
    def quantity_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("Quantity must be at least 1")
        return v

    @field_validator("target_item_id")
    @classmethod
    def item_id_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("Invalid item ID")
        return v


@router.post("/refresh/items")
async def post_refresh_items(max_pages: int = 0, background: bool = False):
    if background:
        task_id = uuid.uuid4().hex[:12]
        import asyncio

        asyncio.create_task(refresh_items(max_pages=max_pages, task_id=task_id))
        return {"status": "started", "task_id": task_id}
    count = await refresh_items(max_pages=max_pages)
    return {"status": "ok", "items_refreshed": count}


@router.post("/refresh/recipes")
async def post_refresh_recipes(max_pages: int = 0, background: bool = False):
    if background:
        task_id = uuid.uuid4().hex[:12]
        import asyncio

        asyncio.create_task(refresh_recipes(max_pages=max_pages, task_id=task_id))
        return {"status": "started", "task_id": task_id}
    count = await refresh_recipes(max_pages=max_pages)
    return {"status": "ok", "recipes_refreshed": count}


@router.get("/refresh/progress/{task_id}")
async def get_refresh_progress(task_id: str):
    progress = get_ingest_progress(task_id)
    if not progress:
        return {"status": "not_found"}
    return progress


@router.get("/recipes/by-output/{item_id}")
async def get_recipes_by_output(item_id: int):
    recipes = await find_recipes_by_output(item_id)
    return recipes


@router.post("/calculate/cheapest", response_model=CraftingResponse)
async def post_crafting_calculate_cheapest(request: CraftCalcRequest):
    try:
        result = await calculate_cheapest(
            api_key=request.api_key,
            target_item_id=request.target_item_id,
            quantity=request.quantity,
            use_owned=request.use_owned,
        )
        return result.model_dump()
    except Gw2ApiError as e:
        raise HTTPException(status_code=401, detail=e.message)


@router.post("/plan", response_model=CraftingPlanResult)
async def post_crafting_plan(request: CraftCalcRequest):
    try:
        result = await create_plan(
            api_key=request.api_key,
            target_item_id=request.target_item_id,
            quantity=request.quantity,
            use_owned=request.use_owned,
        )
        return result.model_dump()
    except Gw2ApiError as e:
        raise HTTPException(status_code=401, detail=e.message)


@router.post("/optimize", response_model=RecipeOptimizationResult)
async def post_crafting_optimize(request: OptimizeRequest):
    try:
        result = await optimize(
            api_key=request.api_key,
            target_item_id=request.target_item_id,
            target_count=request.target_count,
            strategy=request.strategy,
            use_owned=request.use_owned,
        )
        return result.model_dump()
    except Gw2ApiError as e:
        raise HTTPException(status_code=401, detail=e.message)


@router.get("/optimize/{result_id}")
async def get_optimize_result(result_id: str):
    return {"result_id": result_id, "note": "In-memory result not persisted yet"}


@router.get("/optimize/{result_id}/shopping-list")
async def get_optimize_shopping_list(result_id: str):
    return {"result_id": result_id, "items": []}


@router.get("/optimize/{result_id}/crafting-steps")
async def get_optimize_crafting_steps(result_id: str):
    return {"result_id": result_id, "steps": []}


@router.get("/optimize/{result_id}/required-disciplines")
async def get_optimize_disciplines(result_id: str):
    return {"result_id": result_id, "disciplines": []}


@router.post("/calculate", response_model=CraftingResponse)
async def post_crafting_calculate(request: CraftCalcRequest):
    try:
        result = await calculate(
            api_key=request.api_key,
            target_item_id=request.target_item_id,
            quantity=request.quantity,
            use_owned=request.use_owned,
        )
        return result.model_dump()
    except Gw2ApiError as e:
        raise HTTPException(status_code=401, detail=e.message)
