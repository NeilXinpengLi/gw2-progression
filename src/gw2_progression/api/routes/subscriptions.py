from fastapi import APIRouter, Body, HTTPException

from gw2_progression.services.delivery_service import deliver_weekly_reports
from gw2_progression.services.subscription_service import (
    cancel_subscription,
    create_subscription,
    get_subscription,
    update_subscription,
)

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


@router.post("")
async def post_subscription(body: dict = Body(...)):
    account_name = body.get("account_name", "")
    email = body.get("email", "")
    report_type = body.get("report_type", "weekly")
    if not account_name:
        raise HTTPException(status_code=422, detail="account_name is required")
    existing = await get_subscription(account_name)
    if existing:
        await update_subscription(account_name, email=email, active=True)
        return {**existing, "email": email, "active": True}
    result = await create_subscription(account_name, email, report_type)
    return result


@router.get("/{account_name}")
async def get_subscription_endpoint(account_name: str):
    sub = await get_subscription(account_name)
    if not sub:
        return {"active": False}
    return sub


@router.delete("/{account_name}")
async def cancel_subscription_endpoint(account_name: str):
    cancelled = await cancel_subscription(account_name)
    if not cancelled:
        raise HTTPException(status_code=404, detail="No active subscription found")
    return {"status": "cancelled"}


@router.post("/deliver")
async def trigger_delivery():
    await deliver_weekly_reports()
    return {"status": "delivery_completed"}
