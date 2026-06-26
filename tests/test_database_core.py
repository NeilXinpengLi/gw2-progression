"""Tests for core database functions."""

from unittest.mock import AsyncMock, patch

import pytest

from gw2_progression.database import (
    CREATE_TABLES,
    close_pool,
    get_db,
    init_db,
    load_value_history,
    release_db,
    save_account_snapshot,
    save_price_snapshot,
    search_latest_holdings,
    using_db,
)
from gw2_progression.models import ItemHolding, ValueSummary


class _FakeRow:
    """Row mock supporting dict-like access for aiosqlite.Row compatibility."""

    def __init__(self, **kw):
        self._data = kw
        for k, v in kw.items():
            setattr(self, k, v)

    def __getitem__(self, key):
        return self._data[key]

    def __iter__(self):
        return iter(self._data.items())

    def keys(self):
        return self._data.keys()


class TestDbInit:
    @pytest.mark.asyncio
    async def test_init_db_creates_tables(self):
        mock_db = AsyncMock()
        mock_db.execute.return_value = AsyncMock()
        with patch("gw2_progression.database._create_connection", AsyncMock(return_value=mock_db)):
            await init_db()
            assert mock_db.execute.call_count > 0
            mock_db.commit.assert_called_once()

    def test_plan_actions_schema_includes_confidence_metadata(self):
        plan_actions_schema = CREATE_TABLES.split("CREATE TABLE IF NOT EXISTS plan_actions", 1)[1]
        plan_actions_schema = plan_actions_schema.split("CREATE TABLE IF NOT EXISTS plan_revisions", 1)[0]
        assert "confidence REAL NOT NULL DEFAULT 0" in plan_actions_schema
        assert "data_sources TEXT NOT NULL DEFAULT '[]'" in plan_actions_schema
        assert "risk_reason TEXT NOT NULL DEFAULT ''" in plan_actions_schema


class TestPool:
    @pytest.mark.asyncio
    async def test_get_db_returns_connection(self):
        with patch("gw2_progression.database._pool", None):
            with patch("gw2_progression.database._create_connection", AsyncMock()) as mock_create:
                mock_conn = AsyncMock()
                mock_conn.commit = AsyncMock()
                mock_conn.rollback = AsyncMock()
                mock_conn.close = AsyncMock()
                mock_create.return_value = mock_conn
                conn = await get_db()
                assert conn is mock_conn
                await close_pool()

    @pytest.mark.asyncio
    async def test_release_db_returns_to_pool(self):
        import asyncio

        pool = asyncio.Queue(5)
        conn = AsyncMock()
        await pool.put(conn)
        with patch("gw2_progression.database._pool", pool):
            await release_db(conn)
            assert pool.qsize() == 2

    @pytest.mark.asyncio
    async def test_using_db_context_manager(self):
        import asyncio

        pool = asyncio.Queue(1)
        conn = AsyncMock()
        conn.commit = AsyncMock()
        conn.rollback = AsyncMock()
        conn.execute = AsyncMock()
        await pool.put(conn)
        with patch("gw2_progression.database._pool", pool):
            async with using_db() as db:
                assert db is conn
        conn.commit.assert_called_once()


class TestSearchHoldings:
    @pytest.mark.asyncio
    async def test_search_latest_holdings_empty(self):
        mock_db = AsyncMock()
        cursor = AsyncMock()
        cursor.fetchall = AsyncMock(return_value=[])
        mock_db.execute = AsyncMock(return_value=cursor)
        results = await search_latest_holdings(mock_db, "Player.Unknown")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_holdings_with_filters(self):
        mock_db = AsyncMock()
        cursor = AsyncMock()
        mock_db.execute = AsyncMock(return_value=cursor)
        cursor.fetchall = AsyncMock(
            return_value=[
                _FakeRow(
                    item_id=19976,
                    count=100,
                    location_type="material_storage",
                    location_ref=None,
                    binding_status=None,
                    tradable=1,
                    vendor_value=0,
                    price_buy=20000,
                    price_sell=21600,
                    value_buy=200000,
                    value_sell=216000,
                    valuation_status="priced",
                )
            ]
        )
        items = await search_latest_holdings(mock_db, "Player.Test", query="19976", limit=10)
        assert len(items) == 1
        assert items[0].item_id == 19976

    @pytest.mark.asyncio
    async def test_search_holdings_by_location(self):
        mock_db = AsyncMock()
        cursor = AsyncMock()
        cursor.fetchall = AsyncMock(return_value=[])
        mock_db.execute = AsyncMock(return_value=cursor)
        await search_latest_holdings(mock_db, "Player.Test", location_type="bank")
        call_args = mock_db.execute.call_args
        assert "location_type" in call_args[0][0]
        assert "bank" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_search_holdings_by_status(self):
        mock_db = AsyncMock()
        cursor = AsyncMock()
        cursor.fetchall = AsyncMock(return_value=[])
        mock_db.execute = AsyncMock(return_value=cursor)
        await search_latest_holdings(mock_db, "Player.Test", valuation_status="account_bound")
        call_args = mock_db.execute.call_args
        assert "valuation_status" in call_args[0][0]


class TestSaveSnapshot:
    @pytest.mark.asyncio
    async def test_save_price_snapshot(self):
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        await save_price_snapshot(mock_db, 19976, 20000, 5000, 21600, 3000)
        assert mock_db.execute.call_count == 1

    @pytest.mark.asyncio
    async def test_save_account_snapshot(self):
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=AsyncMock(lastrowid=42))

        summary = ValueSummary(
            total_value_buy=1000000,
            total_value_sell=1200000,
            net_sell_value=1020000,
            wallet_value=500000,
        )
        holdings = [
            ItemHolding(item_id=19976, count=100, location_type="material_storage", valuation_status="priced", value_buy=200000, value_sell=216000),
        ]

        snapshot_id = await save_account_snapshot(mock_db, "Player.Test", None, summary, holdings, [])
        assert snapshot_id == 42
        assert mock_db.execute.call_count >= 3


class TestValueHistory:
    @pytest.mark.asyncio
    async def test_load_value_history_empty(self):
        mock_db = AsyncMock()
        cursor = AsyncMock()
        cursor.fetchall = AsyncMock(return_value=[])
        mock_db.execute = AsyncMock(return_value=cursor)
        results = await load_value_history(mock_db, "Player.NoHistory")
        assert results == []


class TestClosePool:
    @pytest.mark.asyncio
    async def test_close_pool_closes_connections(self):
        import asyncio

        pool = asyncio.Queue(1)
        conn = AsyncMock()
        conn.close = AsyncMock()
        pool.put_nowait(conn)
        with patch("gw2_progression.database._pool", pool):
            await close_pool()
        conn.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_pool_none(self):
        with patch("gw2_progression.database._pool", None):
            await close_pool()  # should not raise
