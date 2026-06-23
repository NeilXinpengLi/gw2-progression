"""Affiliate service — referral codes, commissions, and payouts."""

import secrets

from gw2_progression.database import using_db


async def create_affiliate(name: str, commission_rate: float = 0.2) -> dict:
    code = secrets.token_hex(4).upper()
    async with using_db() as conn:
        cursor = await conn.execute(
            "INSERT INTO affiliates (name, referral_code, commission_rate) VALUES (?, ?, ?)",
            (name, code, commission_rate),
        )
        return {"id": cursor.lastrowid, "name": name, "referral_code": code, "commission_rate": commission_rate}


async def get_affiliate_by_code(code: str) -> dict | None:
    async with using_db() as conn:
        cursor = await conn.execute("SELECT * FROM affiliates WHERE referral_code = ?", (code,))
        row = await cursor.fetchone()
    if not row:
        return None
    return {"id": row[0], "name": row[1], "referral_code": row[2], "commission_rate": row[3], "total_earned_copper": row[5]}


async def record_referral_sale(affiliate_id: int, order_id: int, commission_copper: int) -> dict:
    async with using_db() as conn:
        cursor = await conn.execute(
            "INSERT INTO referral_sales (affiliate_id, order_id, commission_copper) VALUES (?, ?, ?)",
            (affiliate_id, order_id, commission_copper),
        )
        await conn.execute(
            "UPDATE affiliates SET total_earned_copper = total_earned_copper + ? WHERE id = ?",
            (commission_copper, affiliate_id),
        )
        return {"id": cursor.lastrowid, "affiliate_id": affiliate_id, "commission_copper": commission_copper}


async def get_affiliate_stats(affiliate_id: int) -> dict:
    async with using_db() as conn:
        cursor = await conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(commission_copper), 0) FROM referral_sales WHERE affiliate_id = ?",
            (affiliate_id,),
        )
        row = await cursor.fetchone()
    return {"total_sales": row[0], "total_commission_copper": row[1]}
