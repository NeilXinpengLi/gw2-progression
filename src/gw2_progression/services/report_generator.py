"""PDF Report Generator — commercial report system for paid users."""

from datetime import datetime, timezone

from gw2_progression.services.report_service import generate_report


async def generate_commercial_report(api_key: str, account_name: str = "") -> dict:
    """Generate a full commercial report (PDF content) for paid users."""
    from gw2_progression.analyzer import fetch_all

    contents = await fetch_all(api_key)
    name = account_name or contents.account_name or "unknown"

    wallet_gold = sum(w.get("value", 0) for w in (contents.wallet or []) if w.get("id") == 1)
    chars = contents.characters or []
    char_count = len(chars)
    lvl80 = sum(1 for c in chars if c.get("level") == 80)
    skin_count = contents.unlocked_skins_count or 0

    report = await generate_report(
        account_name=name,
        report_type="commercial",
        title=f"GW2 Account Report — {name}",
        summary=f"Full account analysis for {name}",
        total_value_buy=0,
        wallet_gold=wallet_gold,
        character_count=char_count,
    )

    return {
        "report_id": report.report_id,
        "account_name": name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_value": f"{wallet_gold // 10000}g",
            "characters": f"{char_count} ({lvl80} at 80)",
            "skins": skin_count,
        },
        "sections": ["Account Value", "Top Items", "Build Analysis", "Crafting Path", "7-Day Plan"],
        "raw_report": {
            "report_id": report.report_id,
            "title": report.title,
            "summary": report.summary,
        },
    }


def report_to_html(report_data: dict) -> str:
    """Convert report data to HTML for PDF conversion."""
    s = report_data.get("summary", {})
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{report_data.get("account_name", "Report")}</title>
<style>
body {{ font-family: Arial, sans-serif; background: #0B0F17; color: #e0e0e0; padding: 40px; }}
h1 {{ color: #FFB020; }}
.section {{ background: #121A2A; padding: 16px; margin: 12px 0; border-radius: 8px; }}
.gold {{ color: #FFB020; font-weight: bold; }}
.green {{ color: #2EE59D; }}
</style>
</head><body>
<h1>GW2 Progression Report</h1>
<p>Account: <strong>{report_data.get("account_name", "N/A")}</strong></p>
<p>Generated: {report_data.get("generated_at", "N/A")[:10]}</p>
<div class="section">
<h2>Account Summary</h2>
<p>Total Value: <span class="gold">{s.get("total_value", "0g")}</span></p>
<p>Characters: {s.get("characters", "0")}</p>
<p>Skins: {s.get("skins", "0")}</p>
</div>
<div class="section">
<h2>Report Sections</h2>
<ul>{"".join(f"<li>{sec}</li>" for sec in report_data.get("sections", []))}</ul>
</div>
<p class="green">Full analysis available in your dashboard.</p>
</body></html>"""
