"""Tests for delivery, subscription, and report services."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _acursor(fetch_result=None, fetchall_result=None, lastrowid=1):
    c = MagicMock()
    c.lastrowid = lastrowid
    c.fetchone = AsyncMock(return_value=fetch_result)
    c.fetchall = AsyncMock(return_value=fetchall_result or [])
    return c


# ── Report Service Tests ──


@pytest.mark.asyncio
async def test_generate_report():
    from gw2_progression.services.report_service import generate_report

    with patch("gw2_progression.services.report_service.using_db") as mock_db:
        mock_conn = AsyncMock()
        mock_conn.execute.return_value = _acursor(lastrowid=42)
        mock_db.return_value.__aenter__.return_value = mock_conn

        report = await generate_report(
            account_name="Player.Test",
            report_type="full",
            title="Test Report",
            summary="A test report",
            total_value_buy=1000000,
            total_value_sell=1100000,
            wallet_gold=500000,
            character_count=5,
        )

    assert report.report_id == 42
    assert report.account_name == "Player.Test"
    assert report.total_value_buy == 1000000
    assert report.wallet_gold == 500000
    assert report.character_count == 5


@pytest.mark.asyncio
async def test_list_reports_empty():
    from gw2_progression.services.report_service import list_reports

    with patch("gw2_progression.services.report_service.using_db") as mock_db:
        mock_conn = AsyncMock()
        mock_conn.execute.return_value = _acursor(fetchall_result=[])
        mock_db.return_value.__aenter__.return_value = mock_conn

        reports = await list_reports("Player.Test")
    assert reports == []


@pytest.mark.asyncio
async def test_get_report_not_found():
    from gw2_progression.services.report_service import get_report

    with patch("gw2_progression.services.report_service.using_db") as mock_db:
        mock_conn = AsyncMock()
        mock_conn.execute.return_value = _acursor(fetch_result=None)
        mock_db.return_value.__aenter__.return_value = mock_conn

        report = await get_report(999)
    assert report is None


@pytest.mark.asyncio
async def test_delete_report():
    from gw2_progression.services.report_service import delete_report

    with patch("gw2_progression.services.report_service.using_db") as mock_db:
        mock_conn = AsyncMock()
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_conn.execute.return_value = mock_cursor
        mock_db.return_value.__aenter__.return_value = mock_conn

        result = await delete_report(42)
    assert result is True


# ── Subscription Service Tests ──


@pytest.mark.asyncio
async def test_create_subscription():
    from gw2_progression.services.subscription_service import create_subscription

    with patch("gw2_progression.services.subscription_service.using_db") as mock_db:
        mock_conn = AsyncMock()
        mock_conn.execute.return_value = _acursor(lastrowid=1)
        mock_db.return_value.__aenter__.return_value = mock_conn

        sub = await create_subscription("Player.Test", "test@example.com")

    assert sub["id"] == 1
    assert sub["account_name"] == "Player.Test"
    assert sub["email"] == "test@example.com"


@pytest.mark.asyncio
async def test_get_subscription_not_found():
    from gw2_progression.services.subscription_service import get_subscription

    with patch("gw2_progression.services.subscription_service.using_db") as mock_db:
        mock_conn = AsyncMock()
        mock_conn.execute.return_value = _acursor(fetch_result=None)
        mock_db.return_value.__aenter__.return_value = mock_conn

        sub = await get_subscription("Player.Test")
    assert sub is None


@pytest.mark.asyncio
async def test_cancel_subscription():
    from gw2_progression.services.subscription_service import cancel_subscription

    with patch("gw2_progression.services.subscription_service.using_db") as mock_db:
        mock_conn = AsyncMock()
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_conn.execute.return_value = mock_cursor
        mock_db.return_value.__aenter__.return_value = mock_conn

        result = await cancel_subscription("Player.Test")
    assert result is True


@pytest.mark.asyncio
async def test_get_active_subscriptions():
    from gw2_progression.services.subscription_service import get_active_subscriptions

    with patch("gw2_progression.services.subscription_service.using_db") as mock_db:
        mock_conn = AsyncMock()
        mock_conn.execute.return_value = _acursor(
            fetchall_result=[
                (1, "Player.Test", "test@example.com", "weekly", 1, None, "2026-01-01", "2025-01-01"),
            ]
        )
        mock_db.return_value.__aenter__.return_value = mock_conn

        subs = await get_active_subscriptions()
    assert len(subs) == 1
    assert subs[0]["account_name"] == "Player.Test"


# ── Delivery Service Tests ──


@pytest.mark.asyncio
async def test_deliver_weekly_reports_no_subscriptions():
    from gw2_progression.services.delivery_service import deliver_weekly_reports

    with patch("gw2_progression.services.delivery_service.get_active_subscriptions", AsyncMock(return_value=[])):
        result = await deliver_weekly_reports()
    # Should return without error even with no subscriptions
    assert result is None


def test_send_email_smtp_not_configured():
    """When SMTP is not configured, _send_email should log but not throw."""
    from gw2_progression.services.delivery_service import _send_email

    report = MagicMock()
    report.account_name = "Player.Test"
    report.total_value_buy = 1000000
    report.summary = "Test"
    report.recommendations = []
    report.created_at = "2026-01-01"
    report.title = "Test Report"

    # Should not raise even though SMTP is not configured
    _send_email("test@example.com", report)
    assert True
