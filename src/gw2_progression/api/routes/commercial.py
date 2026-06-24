"""Commercial API — report generation, payment, and delivery."""

from fastapi import APIRouter, Body, HTTPException

router = APIRouter(prefix="/commercial", tags=["commercial"])


@router.post("/report/generate")
async def generate_commercial(body: dict = Body(...)):
    """Generate a full commercial report (requires valid license or payment)."""
    from gw2_progression.services.report_generator import generate_commercial_report

    api_key = body.get("api_key", "")
    license_key = body.get("license_key", "")
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
        report = await generate_commercial_report(api_key, body.get("account_name"))
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/report/html")
async def get_report_html(body: dict = Body(...)):
    """Get HTML version of a report (for PDF conversion)."""
    from gw2_progression.services.report_generator import generate_commercial_report, report_to_html

    api_key = body.get("api_key", "")
    if not api_key:
        raise HTTPException(status_code=422, detail="api_key required")

    report = await generate_commercial_report(api_key, body.get("account_name"))
    html = report_to_html(report)
    return {"html": html, "account_name": report["account_name"], "generated_at": report["generated_at"]}
