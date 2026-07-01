from unittest.mock import AsyncMock

import pytest

from gw2_progression.models import AccountReport


@pytest.mark.asyncio
async def test_delivery_outbox_sends_once_and_recovers_pending_job(commerce_db, monkeypatch):
    from gw2_progression.database import using_db
    from gw2_progression.services.commerce_service import create_order, process_pending_deliveries

    order = await create_order(1, "buyer@example.com", "Buyer", idempotency_key="checkout:delivery")
    report = AccountReport(
        report_id=900,
        account_name="Buyer",
        report_type="product",
        title="Report",
        summary="Ready",
        created_at="2026-07-01",
    )
    monkeypatch.setattr("gw2_progression.services.report_service.generate_report", AsyncMock(return_value=report))
    sent: list[str] = []
    monkeypatch.setattr("gw2_progression.services.delivery_service._send_email", lambda email, _report: sent.append(email))

    await process_pending_deliveries()
    await process_pending_deliveries()

    async with using_db() as conn:
        jobs = await (await conn.execute("SELECT COUNT(*) FROM delivery_jobs WHERE order_id = ?", (order["order_id"],))).fetchone()
        outbox = await (await conn.execute("SELECT COUNT(*), MIN(status) FROM delivery_outbox")).fetchone()

    assert jobs[0] == 1
    assert outbox[0] == 1
    assert outbox[1] == "sent"
    assert sent == ["buyer@example.com"]

