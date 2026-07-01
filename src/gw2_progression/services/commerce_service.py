"""Order service — process purchases and create licenses."""

import json
import logging
import secrets
import sqlite3
from datetime import datetime, timezone
from types import SimpleNamespace

from gw2_progression.database import using_db
from gw2_progression.services.product_service import get_product

logger = logging.getLogger("gw2.commerce")


def _generate_license_key() -> str:
    return f"GWR-{secrets.token_hex(8).upper()[:8]}-{secrets.token_hex(4).upper()}"


def _order_result(order_id: int, license_key: str, license_id: int | None, product_id: int, amount_copper: int, status: str, idempotent_replay: bool = False) -> dict:
    return {
        "order_id": order_id,
        "license_key": license_key,
        "license_id": license_id,
        "product_id": product_id,
        "amount_copper": amount_copper,
        "status": status,
        "idempotent_replay": idempotent_replay,
    }


async def _fetch_order_by_idempotency(conn, idempotency_key: str) -> dict | None:
    cursor = await conn.execute(
        """SELECT o.id, o.product_id, o.amount_copper, o.status, o.license_key, l.id
           FROM order_idempotency_keys k
           JOIN orders o ON o.id = k.order_id
           LEFT JOIN licenses l ON l.order_id = o.id
           WHERE k.idempotency_key = ?""",
        (idempotency_key,),
    )
    existing = await cursor.fetchone()
    if not existing:
        return None
    return _order_result(
        order_id=existing[0],
        license_key=existing[4],
        license_id=existing[5],
        product_id=existing[1],
        amount_copper=existing[2],
        status=existing[3],
        idempotent_replay=True,
    )


async def create_order(product_id: int, customer_email: str, customer_name: str = "", idempotency_key: str = "") -> dict:
    product = await get_product(product_id)
    if not product:
        raise ValueError(f"Product {product_id} not found")

    license_key = _generate_license_key()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    idem_key = idempotency_key.strip()

    async with using_db() as conn:
        if idem_key:
            await conn.execute("BEGIN IMMEDIATE")
            existing = await _fetch_order_by_idempotency(conn, idem_key)
            if existing:
                return existing

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
        row = await cursor.fetchone()
        license_id = row[0] if row else None

        # Create delivery job
        await conn.execute(
            """INSERT OR IGNORE INTO delivery_jobs (order_id, product_id, status)
               VALUES (?, ?, 'pending')""",
            (order_id, product_id),
        )

        if idem_key:
            try:
                await conn.execute(
                    """INSERT INTO order_idempotency_keys
                       (idempotency_key, order_id, status, created_at, fulfilled_at)
                       VALUES (?, ?, 'fulfilled', ?, ?)""",
                    (idem_key, order_id, now, now),
                )
            except sqlite3.IntegrityError:
                existing = await _fetch_order_by_idempotency(conn, idem_key)
                if existing:
                    return existing
                raise

    return _order_result(order_id, license_key, license_id, product_id, product["price_copper"], "paid")


async def record_payment_event_received(
    provider_event_id: str,
    event_type: str,
    idempotency_key: str,
    product_id: int = 0,
    customer_email: str = "",
    provider: str = "stripe",
) -> dict:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    async with using_db() as conn:
        await conn.execute(
            """INSERT OR IGNORE INTO payment_events
               (provider_event_id, provider, event_type, status, idempotency_key, product_id, customer_email, received_at)
               VALUES (?, ?, ?, 'received', ?, ?, ?, ?)""",
            (provider_event_id, provider, event_type, idempotency_key, product_id, customer_email, now),
        )
        cursor = await conn.execute(
            """SELECT provider_event_id, status, order_id, idempotency_key, product_id, customer_email
               FROM payment_events WHERE provider_event_id = ?""",
            (provider_event_id,),
        )
        row = await cursor.fetchone()
    return {
        "provider_event_id": row[0],
        "status": row[1],
        "order_id": row[2],
        "idempotency_key": row[3],
        "product_id": row[4],
        "customer_email": row[5],
        "idempotent_replay": row[1] == "fulfilled",
    }


async def mark_payment_event_fulfilled(provider_event_id: str, order_id: int) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    async with using_db() as conn:
        await conn.execute(
            """UPDATE payment_events
               SET status = 'fulfilled', order_id = ?, error = '', fulfilled_at = ?
               WHERE provider_event_id = ?""",
            (order_id, now, provider_event_id),
        )


async def mark_payment_event_failed(provider_event_id: str, error: str) -> None:
    async with using_db() as conn:
        await conn.execute(
            "UPDATE payment_events SET status = 'failed', error = ? WHERE provider_event_id = ?",
            (error, provider_event_id),
        )


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
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    async with using_db() as conn:
        cursor = await conn.execute(
            """UPDATE licenses
               SET used_count = used_count + 1
               WHERE license_key = ?
                 AND (expires_at IS NULL OR expires_at = '' OR expires_at >= ?)
                 AND (max_uses <= 0 OR used_count < max_uses)""",
            (license_key, now),
        )
        return cursor.rowcount > 0


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


async def process_pending_deliveries(retry_failed: bool = False):
    """Process all pending delivery jobs by generating reports."""
    from gw2_progression.services.report_service import generate_report

    rows = []
    statuses = ("pending", "failed") if retry_failed else ("pending",)
    placeholders = ",".join("?" for _ in statuses)
    async with using_db() as conn:
        cursor = await conn.execute(
            f"""SELECT dj.id, dj.order_id, dj.product_id, o.customer_email, o.customer_name
                FROM delivery_jobs dj JOIN orders o ON dj.order_id = o.id
                WHERE dj.status IN ({placeholders}) LIMIT 10""",
            statuses,
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
                    """INSERT OR IGNORE INTO delivery_outbox
                       (delivery_job_id, order_id, event_type, recipient_email, payload_json, status)
                       VALUES (?, ?, 'email_report', ?, ?, 'pending')""",
                    (
                        job_id,
                        order_id,
                        email,
                        json.dumps(
                            {
                                "report_id": report.report_id,
                                "account_name": report.account_name,
                                "total_value_buy": report.total_value_buy,
                                "summary": report.summary,
                                "recommendations": report.recommendations,
                                "created_at": report.created_at,
                                "title": report.title,
                            }
                        ),
                    ),
                )
                await conn.execute(
                    "UPDATE delivery_jobs SET status = 'done', dashboard_url = ? WHERE id = ?",
                    (f"/reports/{report.report_id}", job_id),
                )
        except Exception as e:
            async with using_db() as conn:
                await conn.execute(
                    "UPDATE delivery_jobs SET status = 'failed', error = ? WHERE id = ?",
                    (str(e), job_id),
                )
    await process_delivery_outbox(retry_failed=retry_failed)


async def process_delivery_outbox(retry_failed: bool = False):
    from gw2_progression.services.delivery_service import _send_email

    statuses = ("pending", "failed") if retry_failed else ("pending",)
    placeholders = ",".join("?" for _ in statuses)
    async with using_db() as conn:
        cursor = await conn.execute(
            f"""SELECT id, recipient_email, payload_json, attempts
                FROM delivery_outbox WHERE status IN ({placeholders}) LIMIT 10""",
            statuses,
        )
        rows = await cursor.fetchall()
    for outbox_id, email, payload_json, attempts in rows:
        try:
            payload = json.loads(payload_json or "{}")
            report = SimpleNamespace(**payload)
            _send_email(email, report)
            now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
            async with using_db() as conn:
                await conn.execute(
                    "UPDATE delivery_outbox SET status = 'sent', sent_at = ?, error = '' WHERE id = ?",
                    (now, outbox_id),
                )
        except Exception as e:
            async with using_db() as conn:
                await conn.execute(
                    "UPDATE delivery_outbox SET status = 'failed', attempts = ?, error = ? WHERE id = ?",
                    (int(attempts or 0) + 1, str(e), outbox_id),
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
