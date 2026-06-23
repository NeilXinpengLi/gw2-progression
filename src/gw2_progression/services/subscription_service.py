"""Subscription service — manage weekly report delivery."""

import logging
from datetime import datetime, timedelta

from gw2_progression.database import using_db

logger = logging.getLogger("gw2.subscription")


async def create_subscription(account_name: str, email: str, report_type: str = "weekly") -> dict:
    next_delivery = (datetime.utcnow() + timedelta(days=7)).isoformat()
    async with using_db() as conn:
        cursor = await conn.execute(
            """INSERT INTO subscriptions (account_name, email, report_type, next_delivery_at)
               VALUES (?, ?, ?, ?)""",
            (account_name, email, report_type, next_delivery),
        )
        return {"id": cursor.lastrowid, "account_name": account_name, "email": email, "report_type": report_type}


async def get_subscription(account_name: str) -> dict | None:
    async with using_db() as conn:
        cursor = await conn.execute(
            "SELECT * FROM subscriptions WHERE account_name = ? ORDER BY created_at DESC LIMIT 1",
            (account_name,),
        )
        row = await cursor.fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "account_name": row[1],
        "email": row[2],
        "report_type": row[3],
        "active": bool(row[4]),
        "last_delivered_at": row[5],
        "next_delivery_at": row[6],
        "created_at": row[7],
    }


async def update_subscription(account_name: str, email: str | None = None, active: bool | None = None) -> bool:
    sets = []
    params = []
    if email is not None:
        sets.append("email = ?")
        params.append(email)
    if active is not None:
        sets.append("active = ?")
        params.append(1 if active else 0)
    if not sets:
        return False
    params.append(account_name)
    async with using_db() as conn:
        cursor = await conn.execute(
            f"UPDATE subscriptions SET {', '.join(sets)} WHERE account_name = ?",
            params,
        )
        return cursor.rowcount > 0


async def cancel_subscription(account_name: str) -> bool:
    return await update_subscription(account_name, active=False)


async def get_active_subscriptions() -> list[dict]:
    rows = []
    async with using_db() as conn:
        cursor = await conn.execute("SELECT * FROM subscriptions WHERE active = 1 AND next_delivery_at <= datetime('now')")
        rows = await cursor.fetchall()
    return [
        {
            "id": r[0],
            "account_name": r[1],
            "email": r[2],
            "report_type": r[3],
            "active": bool(r[4]),
            "last_delivered_at": r[5],
            "next_delivery_at": r[6],
            "created_at": r[7],
        }
        for r in rows
    ]


async def mark_delivered(subscription_id: int) -> None:
    now = datetime.utcnow().isoformat()
    next_delivery = (datetime.utcnow() + timedelta(days=7)).isoformat()
    async with using_db() as conn:
        await conn.execute(
            "UPDATE subscriptions SET last_delivered_at = ?, next_delivery_at = ? WHERE id = ?",
            (now, next_delivery, subscription_id),
        )
