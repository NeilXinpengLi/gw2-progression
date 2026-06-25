"""Commercial API — report generation, payment, products, and delivery.

Supports goal-driven OS reports with plan data, product listing,
and direct checkout with license key generation.
"""

from fastapi import APIRouter, Body, HTTPException

router = APIRouter(prefix="/commercial", tags=["commercial"])


@router.post("/report/generate")
async def generate_commercial(body: dict = Body(...)):
    """Generate a full commercial report (requires valid license or payment).

    Optionally accepts plan_data to include goal-driven action plans in the report.
    """
    from gw2_progression.services.report_generator import generate_commercial_report

    api_key = body.get("api_key", "")
    license_key = body.get("license_key", "")
    plan_data = body.get("plan_data")
    if not api_key:
        raise HTTPException(status_code=422, detail="api_key required")

    # Verify license if provided
    if license_key:
        from gw2_progression.services.commerce_service import use_license, verify_license

        lic = await verify_license(license_key)
        if not lic:
            raise HTTPException(status_code=403, detail="Invalid license key")
        ok = await use_license(license_key)
        if not ok:
            raise HTTPException(status_code=403, detail="License exhausted or expired")

    try:
        report = await generate_commercial_report(api_key, body.get("account_name", ""), plan_data)
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/report/html")
async def get_report_html(body: dict = Body(...)):
    """Get HTML version of a report (for PDF conversion or preview)."""
    from gw2_progression.services.report_generator import generate_commercial_report, report_to_html

    api_key = body.get("api_key", "")
    plan_data = body.get("plan_data")
    if not api_key:
        raise HTTPException(status_code=422, detail="api_key required")

    report = await generate_commercial_report(api_key, body.get("account_name", ""), plan_data)
    html = report_to_html(report)
    return {"html": html, "account_name": report["account_name"], "generated_at": report["generated_at"]}


@router.get("/products")
async def list_products():
    """List all available commercial products."""
    from gw2_progression.services.product_service import list_products

    products = await list_products()
    return {"products": products, "total": len(products)}


@router.post("/checkout")
async def post_checkout(body: dict = Body(...)):
    """Create a direct order with license key generation (no Stripe required).

    For production use, integrate with Stripe via /payment/checkout.
    """
    from gw2_progression.services.commerce_service import create_order

    product_id = body.get("product_id")
    customer_email = body.get("customer_email", "")
    account_name = body.get("account_name", "")

    if not product_id:
        raise HTTPException(status_code=422, detail="product_id is required")
    if not customer_email:
        raise HTTPException(status_code=422, detail="customer_email is required")

    try:
        order = await create_order(product_id, customer_email, account_name)
        return {
            "checkout_url": "",
            "order": order,
            "message": "Order created. Use license_key to access reports.",
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
