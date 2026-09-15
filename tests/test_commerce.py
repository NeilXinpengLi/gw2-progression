"""Tests for commerce, credential, guild, and affiliate services."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _async_cursor(fetch_result=None, fetchall_result=None, lastrowid=1):
    """Create a mock aiosqlite cursor where fetchone/fetchall are async."""
    c = MagicMock()
    c.lastrowid = lastrowid
    if fetch_result is not None:
        c.fetchone = AsyncMock(return_value=fetch_result)
    else:
        c.fetchone = AsyncMock(return_value=None)
    if fetchall_result is not None:
        c.fetchall = AsyncMock(return_value=fetchall_result)
    else:
        c.fetchall = AsyncMock(return_value=[])
    return c


# ── Commerce Service Tests ──


@pytest.mark.asyncio
async def test_create_product_order():
    from gw2_progression.services.commerce_service import create_order

    with (
        patch("gw2_progression.services.commerce_service.get_product") as mock_get,
        patch("gw2_progression.services.commerce_service.using_db") as mock_db,
    ):
        mock_get.return_value = {"id": 1, "slug": "test", "price_copper": 30000}
        mock_conn = AsyncMock()
        mock_conn.execute.return_value = _async_cursor(lastrowid=1)
        mock_db.return_value.__aenter__.return_value = mock_conn

        result = await create_order(1, "test@example.com", "Test User")

    assert result["order_id"] == 1
    assert result["license_key"].startswith("GWR-")
    assert result["amount_copper"] == 30000
    assert result["idempotent_replay"] is False


@pytest.mark.asyncio
async def test_create_order_replays_existing_idempotency_key():
    from gw2_progression.services.commerce_service import create_order

    with (
        patch("gw2_progression.services.commerce_service.get_product") as mock_get,
        patch("gw2_progression.services.commerce_service.using_db") as mock_db,
    ):
        mock_get.return_value = {"id": 1, "slug": "test", "price_copper": 30000}
        mock_conn = AsyncMock()
        mock_conn.execute.return_value = _async_cursor(fetch_result=(42, 1, 30000, "paid", "GWR-EXISTING", 7))
        mock_db.return_value.__aenter__.return_value = mock_conn

        result = await create_order(1, "test@example.com", "Test User", idempotency_key="checkout-123")

    assert result == {
        "order_id": 42,
        "license_key": "GWR-EXISTING",
        "license_id": 7,
        "product_id": 1,
        "amount_copper": 30000,
        "status": "paid",
        "idempotent_replay": True,
    }
    assert mock_conn.execute.call_count == 2
    assert mock_conn.execute.call_args_list[0][0][0] == "BEGIN IMMEDIATE"


@pytest.mark.asyncio
async def test_create_order_records_idempotency_key():
    from gw2_progression.services.commerce_service import create_order

    with (
        patch("gw2_progression.services.commerce_service.get_product") as mock_get,
        patch("gw2_progression.services.commerce_service.using_db") as mock_db,
    ):
        mock_get.return_value = {"id": 1, "slug": "test", "price_copper": 30000}
        mock_conn = AsyncMock()
        mock_conn.execute.side_effect = [
            _async_cursor(),
            _async_cursor(fetch_result=None),
            _async_cursor(lastrowid=42),
            _async_cursor(lastrowid=7),
            _async_cursor(fetch_result=(7,)),
            _async_cursor(lastrowid=3),
            _async_cursor(lastrowid=4),
        ]
        mock_db.return_value.__aenter__.return_value = mock_conn

        result = await create_order(1, "test@example.com", "Test User", idempotency_key="checkout-123")

    assert result["order_id"] == 42
    assert result["license_id"] == 7
    assert "order_idempotency_keys" in mock_conn.execute.call_args_list[-1][0][0]


@pytest.mark.asyncio
async def test_payment_webhook_uses_stripe_event_as_idempotency_key():
    from gw2_progression.services.payment_service import handle_webhook

    event = {
        "id": "evt_123",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_123",
                "metadata": {"product_id": "1"},
                "customer_details": {"email": "test@example.com"},
            }
        },
    }

    with (
        patch("gw2_progression.services.payment_service.STRIPE_WEBHOOK_SECRET", "whsec_test"),
        patch("gw2_progression.services.payment_service.stripe.Webhook.construct_event", return_value=event),
        patch(
            "gw2_progression.services.payment_service.record_payment_event_received",
            AsyncMock(
                return_value={
                    "provider_event_id": "evt_123",
                    "status": "received",
                    "order_id": None,
                    "idempotency_key": "stripe:evt_123",
                    "product_id": 1,
                    "customer_email": "test@example.com",
                    "idempotent_replay": False,
                }
            ),
        ) as mock_receipt,
        patch("gw2_progression.services.payment_service.create_order", AsyncMock(return_value={"order_id": 42, "license_key": "GWR-TEST"})) as mock_create,
        patch("gw2_progression.services.payment_service.mark_payment_event_fulfilled", AsyncMock()) as mock_fulfilled,
    ):
        result = await handle_webhook(b"{}", "sig")

    assert result == "fulfilled"
    mock_receipt.assert_awaited_once()
    mock_create.assert_awaited_once_with(1, "test@example.com", idempotency_key="stripe:evt_123")
    mock_fulfilled.assert_awaited_once_with("evt_123", 42)


@pytest.mark.asyncio
async def test_verify_license():
    from gw2_progression.services.commerce_service import verify_license

    with patch("gw2_progression.services.commerce_service.using_db") as mock_db:
        mock_conn = AsyncMock()
        mock_cursor = _async_cursor(fetch_result=(1, "GWR-TEST", 1, 1, '{"report_type":"test"}', 10, 0, None, "2025-01-01"))
        mock_conn.execute.return_value = mock_cursor
        mock_db.return_value.__aenter__.return_value = mock_conn
        result = await verify_license("GWR-TEST")

    assert result is not None
    assert result["license_key"] == "GWR-TEST"
    assert result["max_uses"] == 10


@pytest.mark.asyncio
async def test_use_license_exhausted():
    from gw2_progression.services.commerce_service import use_license

    with patch("gw2_progression.services.commerce_service.using_db") as mock_db:
        mock_conn = AsyncMock()
        exhausted = MagicMock()
        exhausted.rowcount = 0
        mock_conn.execute.return_value = exhausted
        mock_db.return_value.__aenter__.return_value = mock_conn
        result = await use_license("GWR-EXHAUSTED")
    assert result is False


@pytest.mark.asyncio
async def test_product_list():
    from gw2_progression.services.product_service import list_products

    mock_c = _async_cursor(
        fetchall_result=[
            (1, "test-report", "Test Report", "A test", 30000, "one_time", '["PDF"]', "", 1, "2025-01-01"),
        ]
    )
    with patch("gw2_progression.services.product_service.using_db", return_value=AsyncMock(__aenter__=AsyncMock(return_value=AsyncMock(execute=AsyncMock(return_value=mock_c))))):
        products = await list_products()

    assert len(products) == 1
    assert products[0]["name"] == "Test Report"
    assert products[0]["price_gold"] == 3.0


# ── Credential Service Tests ──


@pytest.mark.asyncio
async def test_save_credential():
    from gw2_progression.services.credential_service import save_credential

    with (
        patch("gw2_progression.services.credential_service.encrypt_value") as mock_enc,
        patch("gw2_progression.services.credential_service.fingerprint") as mock_fp,
        patch("gw2_progression.services.credential_service.using_db") as mock_db,
    ):
        mock_enc.return_value = "encrypted:sk-test"
        mock_fp.return_value = "...test"
        mock_conn = AsyncMock()
        mock_conn.execute.return_value = _async_cursor(lastrowid=1)
        mock_db.return_value.__aenter__.return_value = mock_conn

        result = await save_credential("openai", "sk-test", "My Key")

    assert result["id"] == 1
    assert result["fingerprint"] == "...test"


@pytest.mark.asyncio
async def test_update_credential_status():
    from gw2_progression.services.credential_service import update_credential_status

    with patch("gw2_progression.services.credential_service.using_db") as mock_db:
        mock_conn = AsyncMock()
        mock_db.return_value.__aenter__.return_value = mock_conn
        await update_credential_status(1, "valid", "account,characters")

    call_sql = mock_conn.execute.call_args[0][0]
    call_params = mock_conn.execute.call_args[0][1]
    assert "UPDATE credentials SET status" in call_sql
    assert call_params[0] == "valid"
    assert call_params[1] == "account,characters"


@pytest.mark.asyncio
async def test_record_usage():
    from gw2_progression.services.credential_service import record_usage

    with patch("gw2_progression.services.credential_service.using_db") as mock_db:
        mock_conn = AsyncMock()
        mock_db.return_value.__aenter__.return_value = mock_conn
        await record_usage(1, "gw2_analyze", "gw2", 0)

    assert "INSERT INTO credential_usage" in mock_conn.execute.call_args[0][0]


# ── Guild Service Tests ──


@pytest.mark.asyncio
async def test_create_guild():
    from gw2_progression.services.guild_service import create_guild

    with patch("gw2_progression.services.guild_service.using_db") as mock_db:
        mock_conn = AsyncMock()
        mock_cursor = _async_cursor(lastrowid=1)
        mock_conn.execute.return_value = mock_cursor
        mock_db.return_value.__aenter__.return_value = mock_conn

        result = await create_guild("Test Guild", "Player.1234", "")

    assert result["id"] == 1
    assert result["name"] == "Test Guild"
    assert len(result["invite_code"]) == 12


@pytest.mark.asyncio
async def test_join_guild_invalid_code():
    from gw2_progression.services.guild_service import join_guild

    with patch("gw2_progression.services.guild_service.using_db") as mock_db:
        mock_conn = AsyncMock()
        mock_cursor = _async_cursor(fetch_result=None)
        mock_conn.execute.return_value = mock_cursor
        mock_db.return_value.__aenter__.return_value = mock_conn

        result = await join_guild("INVALID", "Player.5678", "")
    assert result is None


@pytest.mark.asyncio
async def test_get_guild_by_account():
    from gw2_progression.services.guild_service import get_guild_by_account

    mock_c1 = _async_cursor(fetch_result=(1, "Test Guild", "ABCDEF123456"))
    mock_c2 = _async_cursor(fetch_result=(1, "Test Guild", "ABCDEF123456", "2025-01-01"))
    mock_c3 = _async_cursor(fetchall_result=[("Player.1234", "leader", "2025-01-01")])

    with patch("gw2_progression.services.guild_service.using_db") as mock_db:
        mock_conn = AsyncMock()
        mock_conn.execute.side_effect = [mock_c1, mock_c2, mock_c3]
        mock_db.return_value.__aenter__.return_value = mock_conn

        guild = await get_guild_by_account("Player.1234")

    assert guild is not None
    assert guild["name"] == "Test Guild"
    assert len(guild["members"]) == 1


# ── Affiliate Service Tests ──


@pytest.mark.asyncio
async def test_create_affiliate():
    from gw2_progression.services.affiliate_service import create_affiliate

    with patch("gw2_progression.services.affiliate_service.using_db") as mock_db:
        mock_conn = AsyncMock()
        mock_conn.execute.return_value = _async_cursor(lastrowid=1)
        mock_db.return_value.__aenter__.return_value = mock_conn

        result = await create_affiliate("TestStreamer")

    assert result["id"] == 1
    assert result["name"] == "TestStreamer"
    assert len(result["referral_code"]) == 8


@pytest.mark.asyncio
async def test_affiliate_purchase_flow():
    from gw2_progression.services.affiliate_service import create_affiliate, get_affiliate_by_code, record_referral_sale

    mock_c1 = _async_cursor(lastrowid=1)
    mock_c2 = _async_cursor(fetch_result=(1, "TestStreamer", "ABCD1234", 0.2, "", 0, "2025-01-01"))
    mock_c3 = _async_cursor(lastrowid=100)
    # record_referral_sale makes TWO execute calls (INSERT + UPDATE)
    mock_c4 = _async_cursor(lastrowid=100)

    with patch("gw2_progression.services.affiliate_service.using_db") as mock_db:
        mock_conn = AsyncMock()
        mock_conn.execute.side_effect = [mock_c1, mock_c2, mock_c3, mock_c4]
        mock_db.return_value.__aenter__.return_value = mock_conn

        aff = await create_affiliate("TestStreamer")
        found = await get_affiliate_by_code(aff["referral_code"])
        sale = await record_referral_sale(1, 42, 5000)

    assert found["name"] == "TestStreamer"
    assert sale["commission_copper"] == 5000


# ── Provider Service Tests ──


def test_scope_explanations():
    from gw2_progression.services.provider_service import SCOPE_EXPLANATIONS

    ex = SCOPE_EXPLANATIONS
    assert "account" in ex
    assert "characters" in ex
    assert "inventories" in ex
    assert len(ex) >= 10
