import asyncio

import pytest


@pytest.mark.asyncio
async def test_same_idempotency_key_creates_one_order_license_and_delivery(commerce_db):
    from gw2_progression.database import using_db
    from gw2_progression.services.commerce_service import create_order

    results = await asyncio.gather(
        create_order(1, "buyer@example.com", "Buyer", idempotency_key="checkout:one"),
        create_order(1, "buyer@example.com", "Buyer", idempotency_key="checkout:one"),
    )

    assert {result["order_id"] for result in results} == {results[0]["order_id"]}
    assert any(result["idempotent_replay"] for result in results)

    async with using_db() as conn:
        order_count = (await (await conn.execute("SELECT COUNT(*) FROM orders")).fetchone())[0]
        license_count = (await (await conn.execute("SELECT COUNT(*) FROM licenses")).fetchone())[0]
        delivery_count = (await (await conn.execute("SELECT COUNT(*) FROM delivery_jobs")).fetchone())[0]
        idem_count = (await (await conn.execute("SELECT COUNT(*) FROM order_idempotency_keys")).fetchone())[0]

    assert order_count == 1
    assert license_count == 1
    assert delivery_count == 1
    assert idem_count == 1
