import pytest


@pytest.mark.asyncio
async def test_replayed_stripe_event_fulfills_once(commerce_db, monkeypatch):
    from gw2_progression.database import using_db
    from gw2_progression.services import payment_service

    event = {
        "id": "evt_once",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_once",
                "metadata": {"product_id": "1"},
                "customer_details": {"email": "buyer@example.com"},
            }
        },
    }
    monkeypatch.setattr(payment_service, "STRIPE_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setattr(payment_service.stripe.Webhook, "construct_event", lambda payload, sig, secret: event)

    first = await payment_service.handle_webhook(b"{}", "sig")
    second = await payment_service.handle_webhook(b"{}", "sig")

    assert first == "fulfilled"
    assert second == "fulfilled"
    async with using_db() as conn:
        order_count = (await (await conn.execute("SELECT COUNT(*) FROM orders")).fetchone())[0]
        event_row = await (
            await conn.execute("SELECT status, order_id FROM payment_events WHERE provider_event_id = 'evt_once'")
        ).fetchone()

    assert order_count == 1
    assert event_row["status"] == "fulfilled"
    assert event_row["order_id"] is not None

