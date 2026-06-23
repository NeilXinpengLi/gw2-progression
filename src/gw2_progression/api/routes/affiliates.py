from fastapi import APIRouter, Body, HTTPException

from gw2_progression.services.affiliate_service import (
    create_affiliate,
    get_affiliate_by_code,
    get_affiliate_stats,
    record_referral_sale,
)
from gw2_progression.services.commerce_service import create_order

router = APIRouter(prefix="/affiliates", tags=["affiliates"])


@router.post("")
async def post_affiliate(body: dict = Body(...)):
    name = body.get("name", "")
    if not name:
        raise HTTPException(status_code=422, detail="name is required")
    rate = body.get("commission_rate", 0.2)
    aff = await create_affiliate(name, rate)
    return aff


@router.get("/{code}")
async def get_affiliate(code: str):
    aff = await get_affiliate_by_code(code)
    if not aff:
        raise HTTPException(status_code=404, detail="Affiliate not found")
    return aff


@router.get("/{affiliate_id}/stats")
async def get_stats(affiliate_id: int):
    return await get_affiliate_stats(affiliate_id)


@router.post("/purchase")
async def post_affiliate_purchase(body: dict = Body(...)):
    referral_code = body.get("referral_code", "")
    product_id = body.get("product_id")
    customer_email = body.get("customer_email", "")
    if not referral_code or not product_id or not customer_email:
        raise HTTPException(status_code=422, detail="referral_code, product_id, and customer_email required")

    aff = await get_affiliate_by_code(referral_code)
    if not aff:
        raise HTTPException(status_code=404, detail="Invalid referral code")

    from gw2_progression.services.product_service import get_product

    product = await get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    commission = int(product["price_copper"] * aff["commission_rate"])
    order = await create_order(product_id, customer_email)
    await record_referral_sale(aff["id"], order["order_id"], commission)

    return {**order, "commission_copper": commission, "affiliate": aff["name"]}
