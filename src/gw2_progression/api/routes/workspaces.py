from fastapi import APIRouter, Body, HTTPException

from gw2_progression.services.workspace_service import (
    add_member,
    create_workspace,
    get_workspace,
    list_workspaces,
    remove_member,
)

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.post("")
async def post_workspace(body: dict = Body(...)):
    name = body.get("name", "")
    owner = body.get("account_name", "")
    if not name or not owner:
        raise HTTPException(status_code=422, detail="name and account_name required")
    return await create_workspace(name, owner)


@router.get("")
async def get_workspaces(account_name: str):
    return await list_workspaces(account_name)


@router.get("/{workspace_id}")
async def get_workspace_by_id(workspace_id: int):
    ws = await get_workspace(workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return ws


@router.post("/{workspace_id}/members")
async def post_member(workspace_id: int, body: dict = Body(...)):
    account_name = body.get("account_name", "")
    role = body.get("role", "member")
    if not account_name:
        raise HTTPException(status_code=422, detail="account_name required")
    ok = await add_member(workspace_id, account_name, role)
    if not ok:
        raise HTTPException(status_code=409, detail="Already a member")
    return {"status": "added", "account_name": account_name, "role": role}


@router.delete("/{workspace_id}/members/{account_name}")
async def delete_member(workspace_id: int, account_name: str):
    ok = await remove_member(workspace_id, account_name)
    if not ok:
        raise HTTPException(status_code=404, detail="Not a member or is admin")
    return {"status": "removed"}
