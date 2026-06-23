"""Order service — process purchases and create licenses."""

import json
import logging
import secrets
from datetime import datetime

from gw2_progression.database import using_db
from gw2_progression.services.product_service import get_product

logger = logging.getLogger("gw2.commerce")


def _generate_license_key() -> str:
    return f"GWR-{secrets.token_hex(8).upper()[:8]}-{secrets.token_hex(4).upper()}"


async def create_order(product_id: int, customer_email: str, customer_name: str = "") -> dict:
    product = await get_product(product_id)
    if not product:
        raise ValueError(f"Product {product_id} not found")

    license_key = _generate_license_key()
    now = datetime.utcnow().isoformat()

    async with using_db() as conn:
        cursor = await conn.execute(
            """INSERT INTO orders (product_id, customer_email, customer_name, amount_copper, status, license_key, created_at)
               VALUES (?, ?, ?, ?, 'paid', ?, ?)""",
            (product_id, customer_email, customer_name, product["price_copper"], license_key, now),
        )
        order_id = cursor.lastrowid

        feature_flags = json.dumps(
            {
                "report_type": product["slug"],
                "max_downloads": 10,
            }
        )
        await conn.execute(
            """INSERT INTO licenses (license_key, product_id, order_id, feature_flags, max_uses)
               VALUES (?, ?, ?, ?, 10)""",
            (license_key, product_id, order_id, feature_flags),
        )
        cursor = await conn.execute("SELECT last_insert_rowid()")
        license_id = cursor.lastrowid

        # Create delivery job
        await conn.execute(
            """INSERT INTO delivery_jobs (order_id, product_id, status)
               VALUES (?, ?, 'pending')""",
            (order_id, product_id),
        )

    return {
        "order_id": order_id,
        "license_key": license_key,
        "license_id": license_id,
        "product_id": product_id,
        "amount_copper": product["price_copper"],
        "status": "paid",
    }


async def verify_license(license_key: str) -> dict | None:
    async with using_db() as conn:
        cursor = await conn.execute("SELECT * FROM licenses WHERE license_key = ?", (license_key,))
        row = await cursor.fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "license_key": row[1],
        "product_id": row[2],
        "order_id": row[3],
        "feature_flags": json.loads(row[4]) if row[4] else {},
        "max_uses": row[5],
        "used_count": row[6],
        "expires_at": row[7],
        "created_at": row[8],
    }


async def use_license(license_key: str) -> bool:
    lic = await verify_license(license_key)
    if not lic:
        return False
    if lic["max_uses"] > 0 and lic["used_count"] >= lic["max_uses"]:
        return False
    if lic["expires_at"] and lic["expires_at"] < datetime.utcnow().isoformat():
        return False
    async with using_db() as conn:
        await conn.execute(
            "UPDATE licenses SET used_count = used_count + 1 WHERE license_key = ?",
            (license_key,),
        )
    return True


async def get_orders(customer_email: str | None = None) -> list[dict]:
    rows = []
    async with using_db() as conn:
        if customer_email:
            cursor = await conn.execute(
                "SELECT * FROM orders WHERE customer_email = ? ORDER BY created_at DESC",
                (customer_email,),
            )
        else:
            cursor = await conn.execute("SELECT * FROM orders ORDER BY created_at DESC")
        rows = await cursor.fetchall()
    return [
        {
            "id": r[0],
            "product_id": r[1],
            "customer_email": r[2],
            "customer_name": r[3],
            "amount_copper": r[4],
            "amount_gold": r[4] / 10000,
            "status": r[5],
            "license_key": r[6],
            "created_at": r[7],
        }
        for r in rows
    ]


async def process_pending_deliveries():
    """Process all pending delivery jobs by generating reports."""
    from gw2_progression.services.report_service import generate_report

    rows = []
    async with using_db() as conn:
        cursor = await conn.execute(
            "SELECT dj.id, dj.order_id, dj.product_id, o.customer_email, o.customer_name FROM delivery_jobs dj JOIN orders o ON dj.order_id = o.id WHERE dj.status = 'pending' LIMIT 10"
        )
        rows = await cursor.fetchall()
    for row in rows:
        job_id, order_id, product_id, email, name = row
        try:
            report = await generate_report(
                account_name=name or "customer",
                report_type="product",
                title=f"Order #{order_id} Report",
                summary=f"Your ordered report (#{product_id}) has been generated.",
            )
            async with using_db() as conn:
                await conn.execute(
                    "UPDATE delivery_jobs SET status = 'done', dashboard_url = ? WHERE id = ?",
                    (f"/reports/{report.report_id}", job_id),
                )
            from gw2_progression.services.delivery_service import _send_email

            _send_email(email, report)
        except Exception as e:
            async with using_db() as conn:
                await conn.execute(
                    "UPDATE delivery_jobs SET status = 'failed', error = ? WHERE id = ?",
                    (str(e), job_id),
                )


async def get_delivery_jobs(order_id: int | None = None) -> list[dict]:
    rows = []
    async with using_db() as conn:
        if order_id:
            cursor = await conn.execute(
                "SELECT * FROM delivery_jobs WHERE order_id = ? ORDER BY created_at DESC",
                (order_id,),
            )
        else:
            cursor = await conn.execute("SELECT * FROM delivery_jobs ORDER BY created_at DESC")
        rows = await cursor.fetchall()
    return [
        {
            "id": r[0],
            "order_id": r[1],
            "product_id": r[2],
            "status": r[3],
            "output_pdf_url": r[4],
            "output_csv_url": r[5],
            "dashboard_url": r[6],
            "error": r[7],
            "created_at": r[8],
        }
        for r in rows
    ]
