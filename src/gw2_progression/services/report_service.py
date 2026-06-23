import json
import logging
from datetime import datetime

from gw2_progression.database import using_db
from gw2_progression.models import AccountReport

logger = logging.getLogger("gw2.report")


def _row_to_report(row: tuple) -> AccountReport:
    return AccountReport(
        report_id=row[0],
        account_name=row[1],
        report_type=row[2],
        title=row[3],
        summary=row[4],
        total_value_buy=row[5],
        total_value_sell=row[6],
        wallet_gold=row[7],
        character_count=row[8],
        goal_count=row[9],
        goal_progress_pct=row[10],
        build_readiness_pct=row[11],
        top_items=json.loads(row[12]) if row[12] else [],
        goal_details=json.loads(row[13]) if row[13] else [],
        build_details=json.loads(row[14]) if row[14] else [],
        recommendations=json.loads(row[15]) if row[15] else [],
        snapshot_time=row[16],
        created_at=row[17],
    )


async def generate_report(
    account_name: str,
    report_type: str,
    title: str = "",
    summary: str = "",
    total_value_buy: int = 0,
    total_value_sell: int = 0,
    wallet_gold: int = 0,
    character_count: int = 0,
    goal_count: int = 0,
    goal_progress_pct: float = 0.0,
    build_readiness_pct: float = 0.0,
    top_items: list[dict] | None = None,
    goal_details: list[dict] | None = None,
    build_details: list[dict] | None = None,
    recommendations: list[str] | None = None,
    snapshot_time: str | None = None,
) -> AccountReport:
    top_items_json = json.dumps(top_items or [], ensure_ascii=False)
    goal_details_json = json.dumps(goal_details or [], ensure_ascii=False)
    build_details_json = json.dumps(build_details or [], ensure_ascii=False)
    recommendations_json = json.dumps(recommendations or [], ensure_ascii=False)
    now = datetime.utcnow().isoformat()

    async with using_db() as conn:
        cursor = await conn.execute(
            """INSERT INTO reports
               (account_name, report_type, title, summary,
                total_value_buy, total_value_sell, wallet_gold,
                character_count, goal_count, goal_progress_pct,
                build_readiness_pct, top_items, goal_details,
                build_details, recommendations, snapshot_time, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                account_name,
                report_type,
                title,
                summary,
                total_value_buy,
                total_value_sell,
                wallet_gold,
                character_count,
                goal_count,
                goal_progress_pct,
                build_readiness_pct,
                top_items_json,
                goal_details_json,
                build_details_json,
                recommendations_json,
                snapshot_time,
                now,
            ),
        )
        report_id = cursor.lastrowid
    return AccountReport(
        report_id=report_id,
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
        top_items=top_items or [],
        goal_details=goal_details or [],
        build_details=build_details or [],
        recommendations=recommendations or [],
        snapshot_time=snapshot_time or "",
        created_at=now,
    )


async def list_reports(account_name: str, limit: int = 20) -> list[AccountReport]:
    rows = []
    async with using_db() as conn:
        cursor = await conn.execute(
            "SELECT * FROM reports WHERE account_name = ? ORDER BY created_at DESC LIMIT ?",
            (account_name, limit),
        )
        rows = await cursor.fetchall()
    return [_row_to_report(r) for r in rows]


async def get_report(report_id: int) -> AccountReport | None:
    async with using_db() as conn:
        cursor = await conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,))
        row = await cursor.fetchone()
    return _row_to_report(row) if row else None


async def delete_report(report_id: int) -> bool:
    async with using_db() as conn:
        cursor = await conn.execute("DELETE FROM reports WHERE id = ?", (report_id,))
        return cursor.rowcount > 0
