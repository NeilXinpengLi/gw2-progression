import asyncio

import pytest


@pytest.mark.asyncio
async def test_concurrent_license_use_does_not_exceed_max_uses(commerce_db):
    from gw2_progression.database import using_db
    from gw2_progression.services.commerce_service import use_license

    async with using_db() as conn:
        await conn.execute(
            """INSERT INTO licenses (license_key, product_id, feature_flags, max_uses, used_count)
               VALUES ('GWR-ATOMIC', 1, '{}', 1, 0)"""
        )

    results = await asyncio.gather(use_license("GWR-ATOMIC"), use_license("GWR-ATOMIC"))

    async with using_db() as conn:
        row = await (await conn.execute("SELECT used_count FROM licenses WHERE license_key = 'GWR-ATOMIC'")).fetchone()

    assert results.count(True) == 1
    assert results.count(False) == 1
    assert row["used_count"] == 1

