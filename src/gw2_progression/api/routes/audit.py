from fastapi import APIRouter, Query

from gw2_progression.services.audit_service import get_audit_log

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/log")
async def get_log(limit: int = Query(50, ge=1, le=200), action: str | None = None):
    return await get_audit_log(limit, action)
