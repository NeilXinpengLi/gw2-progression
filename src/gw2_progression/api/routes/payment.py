from fastapi import APIRouter, Body, HTTPException, Request

from gw2_progression.services.payment_service import (
    create_checkout_session,
    handle_webhook,
)

router = APIRouter(prefix="/payment", tags=["payment"])


@router.post("/checkout")
async def post_checkout(body: dict = Body(...)):
    product_id = body.get("product_id")
    customer_email = body.get("customer_email", "")
    success_url = body.get("success_url", "/?payment=success")
    cancel_url = body.get("cancel_url", "/?payment=cancelled")
    if not product_id or not customer_email:
        raise HTTPException(status_code=422, detail="product_id and customer_email required")

    url = await create_checkout_session(product_id, customer_email, success_url, cancel_url)
    if not url:
        raise HTTPException(status_code=500, detail="Failed to create checkout session")
    return {"checkout_url": url}


@router.post("/webhook")
async def post_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    result = await handle_webhook(payload, sig_header)
    return {"status": result}
