"""PDF Report Generator — enhanced for goal-driven OS reports.

Generates full progression reports with account valuation,
goal progress, build readiness, and 7-day plan.
"""

import logging
from datetime import datetime, timezone

from gw2_progression.services.report_service import generate_report

logger = logging.getLogger("gw2.report_generator")


async def generate_commercial_report(api_key: str, account_name: str = "", plan_data: dict | None = None) -> dict:
    """Generate a full commercial report using account data and optional plan data."""
    from gw2_progression.analyzer import fetch_all

    contents = await fetch_all(api_key)
    name = account_name or contents.account_name or "unknown"

    wallet_gold = sum(w.get("value", 0) for w in (contents.wallet or []) if w.get("id") == 1)
    chars = contents.characters or []
    char_count = len(chars)
    lvl80 = sum(1 for c in chars if c.get("level") == 80)
    skin_count = contents.unlocked_skins_count or 0

    # Try to get valuation data
    total_value_buy = 0
    total_value_sell = 0
    try:
        from gw2_progression.services.holdings_service import (
            extract_bank_holdings,
            extract_character_holdings,
            extract_material_holdings,
            extract_wallet_holdings,
        )
        from gw2_progression.services.price_service import fetch_prices
        from gw2_progression.services.valuation_service import apply_prices, compute_summary

        holdings = []
        holdings.extend(extract_wallet_holdings(contents.wallet or []))
        holdings.extend(extract_material_holdings(contents.materials or []))
        holdings.extend(extract_bank_holdings(contents.bank or []))
        holdings.extend(extract_character_holdings(chars))
        item_ids = list(set(h.item_id for h in holdings))
        prices = await fetch_prices(item_ids)
        holdings = apply_prices(holdings, prices)
        summary = compute_summary(holdings)
        total_value_buy = summary.total_value_buy
        total_value_sell = summary.total_value_sell
    except Exception as e:
        logger.warning("Valuation in report failed: %s", e)

    # Get goal progress
    goal_count = 0
    goal_progress_pct = 0.0
    goal_details = []
    try:
        from gw2_progression.services.progression_service import CURATED_TEMPLATES, generate_goal_plan

        for t in CURATED_TEMPLATES[:5]:
            try:
                gp = await generate_goal_plan(api_key, t.template_id)
                if gp.total_completion_percent > 0:
                    goal_count += 1
                    if gp.total_completion_percent > goal_progress_pct:
                        goal_progress_pct = gp.total_completion_percent
                    goal_details.append({
                        "name": t.name,
                        "progress": gp.total_completion_percent,
                        "missing_cost": gp.total_missing_cost // 10000,
                        "owned": gp.total_owned_material_value // 10000,
                    })
            except Exception:
                continue
    except Exception as e:
        logger.warning("Goal analysis in report failed: %s", e)

    # Get build readiness
    build_readiness_pct = 0.0
    build_details = []
    try:
        from gw2_progression.services.build_service import get_recommendations

        recs = await get_recommendations(api_key)
        if recs:
            best = recs[0]
            build_readiness_pct = best.readiness_score
            for r in recs[:3]:
                build_details.append({
                    "name": r.build_name,
                    "readiness": r.readiness_score * 100,
                    "missing_items": r.missing_items_count,
                    "missing_cost": r.missing_cost // 10000,
                })
    except Exception as e:
        logger.warning("Build analysis in report failed: %s", e)

    # Build recommendations
    recommendations = []
    if plan_data:
        plan = plan_data.get("plan")
        if plan and plan.get("actions"):
            for a in plan["actions"][:3]:
                recommendations.append(f"{a.get('title', '')} — {a.get('reason', '')}")
    if not recommendations:
        if goal_progress_pct > 50:
            recommendations.append(f"Continue your closest goal ({goal_progress_pct:.0f}% complete)")
        if build_readiness_pct > 0.5:
            recommendations.append(f"Equip {build_details[0]['name'] if build_details else 'your build'} ({build_readiness_pct:.0%} readiness)")
        if wallet_gold < 100000:
            recommendations.append("Focus on gold generation through T4 fractals and daily achievements")
        recommendations.append("Review and sell excess materials from storage")

    # Generate top items
    top_items = []
    try:
        from gw2_progression.services.holdings_service import (
            extract_bank_holdings,
            extract_character_holdings,
            extract_material_holdings,
            extract_wallet_holdings,
        )
        from gw2_progression.services.price_service import fetch_prices
        from gw2_progression.services.valuation_service import compute_top_items

        holdings = []
        holdings.extend(extract_material_holdings(contents.materials or []))
        holdings.extend(extract_bank_holdings(contents.bank or []))
        item_ids = list(set(h.item_id for h in holdings))
        prices = await fetch_prices(item_ids)
        holdings = apply_prices(holdings, prices)
        top = compute_top_items(holdings, limit=5)
        for item in top:
            top_items.append({
                "item_id": item.item_id,
                "count": item.count,
                "value_buy": item.value_buy // 10000,
            })
    except Exception:
        pass

    now = datetime.now(timezone.utc).isoformat()
    sections = ["Account Summary", "Total Value", "Top Assets", "Build Analysis", "Goal Progress", "7-Day Plan"]
    if plan_data:
        sections.append("Action Plan")
    sections.append("Recommendations")

    report = await generate_report(
        account_name=name,
        report_type="commercial" if plan_data else "full",
        title=f"GW2 Progression OS Report — {name}",
        summary=f"Full goal-driven account analysis for {name}. Generated {now[:10]}.",
        total_value_buy=total_value_buy,
        total_value_sell=total_value_sell,
        wallet_gold=wallet_gold,
        character_count=char_count,
        goal_count=goal_count,
        goal_progress_pct=goal_progress_pct,
        build_readiness_pct=build_readiness_pct,
        top_items=top_items,
        goal_details=goal_details,
        build_details=build_details,
        recommendations=recommendations,
        snapshot_time=now,
    )

    return {
        "report_id": report.report_id,
        "account_name": name,
        "generated_at": now,
        "summary": {
            "total_value_display": f"{total_value_buy // 10000}g",
            "wallet_display": f"{wallet_gold // 10000}g",
            "characters": f"{char_count} ({lvl80} at 80)",
            "skins": skin_count,
            "goal_count": goal_count,
            "best_goal_progress": round(goal_progress_pct, 1),
            "best_build_readiness": round(build_readiness_pct * 100, 1),
        },
        "sections": sections,
        "top_items": top_items,
        "goal_details": goal_details,
        "build_details": build_details,
        "recommendations": recommendations,
        "plan_summary": {
            "action_count": len(plan_data.get("plan", {}).get("actions", [])) if plan_data else 0,
            "estimated_days": plan_data.get("plan", {}).get("estimated_days", 0) if plan_data else 0,
            "strategy": plan_data.get("plan", {}).get("strategy", "") if plan_data else "",
        } if plan_data else None,
        "report": report,
        "html": _report_to_html(
            name, now, total_value_buy, wallet_gold, char_count, lvl80,
            skin_count, goal_count, goal_progress_pct, build_readiness_pct,
            top_items, goal_details, build_details, recommendations, plan_data,
        ),
    }


def _report_to_html(
    name: str, now: str, total_value: int, wallet_gold: int,
    char_count: int, lvl80: int, skin_count: int,
    goal_count: int, goal_progress: float, build_readiness: float,
    top_items: list, goal_details: list, build_details: list,
    recommendations: list[str], plan_data: dict | None,
) -> str:
    """Generate HTML report for PDF conversion."""
    date_str = now[:10] if now else "Unknown"
    total_g = total_value // 10000
    wallet_g = wallet_gold // 10000

    items_html = "".join(
        f"<tr><td>#{i['item_id']}</td><td>{i['count']}x</td><td class='gold'>{i['value_buy']}g</td></tr>"
        for i in top_items[:5]
    ) if top_items else "<tr><td colspan='3'>No data</td></tr>"

    rec_html = "".join(f"<li>{r}</li>" for r in recommendations[:5])

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>GW2 Progression Report — {name}</title>
<style>
body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #0B0F17; color: #e0e0e0; padding: 40px; max-width: 800px; margin: 0 auto; }}
h1 {{ color: #FFB020; font-size: 28px; border-bottom: 2px solid #FFB020; padding-bottom: 8px; }}
h2 {{ color: #FFB020; font-size: 18px; margin-top: 24px; }}
.section {{ background: #121A2A; padding: 16px; margin: 12px 0; border-radius: 8px; border: 1px solid #2A3A4A; }}
.grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
.card {{ background: #1A2232; padding: 12px; border-radius: 6px; text-align: center; }}
.card .label {{ color: #888; font-size: 11px; text-transform: uppercase; letter-spacing: 1px; }}
.card .value {{ color: #FFB020; font-size: 24px; font-weight: 700; }}
.gold {{ color: #FFB020; font-weight: bold; }}
.green {{ color: #2EE59D; }}
table {{ width: 100%; border-collapse: collapse; margin: 8px 0; }}
th {{ background: #1A2232; color: #888; font-size: 11px; text-transform: uppercase; padding: 8px; text-align: left; }}
td {{ padding: 8px; border-bottom: 1px solid #2A3A4A; }}
.dim {{ color: #888; font-size: 12px; }}
.footer {{ margin-top: 32px; padding-top: 16px; border-top: 1px solid #2A3A4A; font-size: 11px; color: #666; text-align: center; }}
</style>
</head><body>
<h1>GW2 Progression OS Report</h1>
<p class="dim">Account: <strong>{name}</strong> | Generated: {date_str}</p>

<div class="section">
<h2>Account Summary</h2>
<div class="grid">
<div class="card"><div class="label">Total Value</div><div class="value">{total_g}g</div></div>
<div class="card"><div class="label">Liquid Gold</div><div class="value">{wallet_g}g</div></div>
<div class="card"><div class="label">Characters</div><div class="value">{char_count}</div></div>
<div class="card"><div class="label">Skins</div><div class="value">{skin_count}</div></div>
</div>
</div>

<div class="section">
<h2>Top Assets</h2>
<table><thead><tr><th>Item ID</th><th>Count</th><th>Value</th></tr></thead><tbody>{items_html}</tbody></table>
</div>

<div class="section">
<h2>Goal Progress</h2>
<p>Active goals: {goal_count} | Best progress: <span class="gold">{goal_progress:.1f}%</span></p>
{''.join(
    f"<div class='dim'>{g['name']}: {g['progress']:.0f}% (missing: {g['missing_cost']}g)</div>"
    for g in goal_details[:3]
) if goal_details else '<div class="dim">No goals tracked</div>'}
</div>

<div class="section">
<h2>Build Readiness</h2>
<p>Best build readiness: <span class="gold">{build_readiness * 100:.1f}%</span></p>
{''.join(
    f"<div class='dim'>{b['name']}: {b['readiness']:.0f}% (missing {b['missing_items']} items)</div>"
    for b in build_details[:3]
) if build_details else '<div class="dim">No builds analyzed</div>'}
</div>

<div class="section">
<h2>Recommendations</h2>
<ul>{rec_html}</ul>
</div>

{(('<div class="section"><h2>Action Plan</h2>'
    + '<p>Strategy: <strong>' + plan_data.get('plan', {}).get('strategy', 'balanced')
    + '</strong> | Estimated: ' + str(plan_data.get('plan', {}).get('estimated_days', 0))
    + ' days | Actions: ' + str(len(plan_data.get('plan', {}).get('actions', [])))
    + '</p></div>')) if plan_data else ''}

<div class="footer">
<p>Generated by GW2 Progression OS — Goal-Driven Account Intelligence</p>
<p>Data from Guild Wars 2 API. Not affiliated with ArenaNet.</p>
</div>
</body></html>"""


def report_to_html(report_data: dict) -> str:
    """Alias for backward compatibility. Returns the HTML report."""
    return report_data.get("html", "")
