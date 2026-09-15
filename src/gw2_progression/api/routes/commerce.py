from fastapi import APIRouter, Body, Header, HTTPException

from gw2_progression.services.commerce_service import (
    create_order,
    get_delivery_jobs,
    get_orders,
    use_license,
    verify_license,
)
from gw2_progression.services.product_service import get_product, list_products

router = APIRouter(prefix="/commerce", tags=["commerce"])


@router.get("/products")
async def get_products():
    return await list_products()


@router.get("/products/{product_id}")
async def get_product_endpoint(product_id: int):
    product = await get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.post("/orders")
async def post_order(body: dict = Body(...), idempotency_header: str = Header("", alias="Idempotency-Key")):
    product_id = body.get("product_id")
    customer_email = body.get("customer_email", "")
    customer_name = body.get("customer_name", "")
    idempotency_key = body.get("idempotency_key") or idempotency_header
    if not product_id or not customer_email:
        raise HTTPException(status_code=422, detail="product_id and customer_email required")
    try:
        order = await create_order(product_id, customer_email, customer_name, idempotency_key=idempotency_key)
        return order
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/orders")
async def get_orders_endpoint(customer_email: str | None = None):
    return await get_orders(customer_email)


@router.post("/licenses/verify")
async def post_verify_license(body: dict = Body(...)):
    license_key = body.get("license_key", "")
    if not license_key:
        raise HTTPException(status_code=422, detail="license_key required")
    lic = await verify_license(license_key)
    if not lic:
        raise HTTPException(status_code=404, detail="Invalid license key")
    return lic


@router.post("/licenses/use")
async def post_use_license(body: dict = Body(...)):
    license_key = body.get("license_key", "")
    if not license_key:
        raise HTTPException(status_code=422, detail="license_key required")
    ok = await use_license(license_key)
    if not ok:
        raise HTTPException(status_code=403, detail="License exhausted or expired")
    return {"status": "used"}


@router.get("/delivery/{order_id}")
async def get_delivery(order_id: int):
    jobs = await get_delivery_jobs(order_id)
    return jobs
