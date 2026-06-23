from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from gw2_progression.models import AccountReport
from gw2_progression.services.report_service import (
    delete_report,
    generate_report,
    get_report,
    list_reports,
)

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("/generate", response_model=AccountReport)
async def post_generate_report(
    account_name: str = Query(..., description="GW2 account name"),
    report_type: str = Query("full", description="Report type: full, value, goals, builds"),
    title: str = Query("", description="Custom report title"),
    summary: str = Query("", description="Custom summary"),
    total_value_buy: int = Query(0),
    total_value_sell: int = Query(0),
    wallet_gold: int = Query(0),
    character_count: int = Query(0),
    goal_count: int = Query(0),
    goal_progress_pct: float = Query(0.0),
    build_readiness_pct: float = Query(0.0),
):
    report = await generate_report(
        account_name=account_name,
        report_type=report_type,
        title=title,
        summary=summary,
        total_value_buy=total_value_buy,
        total_value_sell=total_value_sell,
        wallet_gold=wallet_gold,
        character_count=character_count,
        goal_count=goal_count,
        goal_progress_pct=goal_progress_pct,
        build_readiness_pct=build_readiness_pct,
        snapshot_time=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
    )
    return report


@router.get("", response_model=list[AccountReport])
async def get_reports(
    account_name: str = Query(..., description="GW2 account name"),
    limit: int = Query(20, ge=1, le=100),
):
    return await list_reports(account_name, limit)


@router.get("/{report_id}", response_model=AccountReport)
async def get_report_by_id(report_id: int):
    report = await get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@router.delete("/{report_id}")
async def delete_report_by_id(report_id: int):
    deleted = await delete_report(report_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Report not found")
    return {"status": "deleted"}
