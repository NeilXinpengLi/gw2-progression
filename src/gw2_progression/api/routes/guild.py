from fastapi import APIRouter, Body, HTTPException

from gw2_progression.services.guild_aggregate import aggregate_guild
from gw2_progression.services.guild_service import (
    create_guild,
    get_guild,
    get_guild_by_account,
    join_guild,
    leave_guild,
)

router = APIRouter(prefix="/guild", tags=["guild"])


@router.post("/create")
async def post_create_guild(body: dict = Body(...)):
    name = body.get("name", "")
    account_name = body.get("account_name", "")
    if not name or not account_name:
        raise HTTPException(status_code=422, detail="name and account_name required")
    guild = await create_guild(name, account_name, "")
    return guild


@router.post("/join")
async def post_join_guild(body: dict = Body(...)):
    invite_code = body.get("invite_code", "")
    account_name = body.get("account_name", "")
    if not invite_code or not account_name:
        raise HTTPException(status_code=422, detail="invite_code and account_name required")
    guild = await join_guild(invite_code, account_name, "")
    if not guild:
        raise HTTPException(status_code=404, detail="Invalid invite code")
    return guild


@router.get("/{guild_id}")
async def get_guild_endpoint(guild_id: int):
    guild = await get_guild(guild_id)
    if not guild:
        raise HTTPException(status_code=404, detail="Guild not found")
    return guild


@router.get("/by-account/{account_name}")
async def get_guild_by_account_endpoint(account_name: str):
    guild = await get_guild_by_account(account_name)
    if not guild:
        return None
    return guild


@router.get("/{guild_id}/aggregate")
async def get_guild_aggregate(guild_id: int):
    return await aggregate_guild(guild_id)


@router.post("/leave")
async def post_leave_guild(body: dict = Body(...)):
    account_name = body.get("account_name", "")
    if not account_name:
        raise HTTPException(status_code=422, detail="account_name required")
    left = await leave_guild(account_name)
    if not left:
        raise HTTPException(status_code=404, detail="Not a member or cannot leave as leader")
    return {"status": "left"}
