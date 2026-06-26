"""Tests for v5 Self-Evolving Learning Engine."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _cursor(fetchone=None, lastrowid=1):
    cursor = MagicMock()
    cursor.fetchone = AsyncMock(return_value=fetchone)
    cursor.lastrowid = lastrowid
    return cursor


def _db_context(conn):
    ctx = AsyncMock()
    ctx.__aenter__.return_value = conn
    return ctx


class TestV5Learning:
    @pytest.mark.asyncio
    async def test_record_experience(self):
        from gw2_progression.services.v5_learning import record_experience

        insert_conn = AsyncMock()
        insert_conn.execute.return_value = _cursor(lastrowid=42)
        update_conn = AsyncMock()
        update_conn.execute.side_effect = [
            _cursor(fetchone=(1, 0.4, 1.0, 0.0, 0.0)),
            _cursor(),
        ]

        with patch("gw2_progression.services.v5_learning.using_db", side_effect=[_db_context(insert_conn), _db_context(update_conn)]):
            result = await record_experience(
                account_name="Test.Player",
                action_key="sell_mystic_coin",
                action_label="Sell Mystic Coin",
                gold_impact=320000,
                success=True,
            )

        assert "experience_id" in result
        assert "reward" in result
        assert result["experience_id"] == 42
        assert result["reward"] > 0

    @pytest.mark.asyncio
    async def test_get_user_model_default(self):
        from gw2_progression.services.v5_learning import get_user_model

        select_conn = AsyncMock()
        select_conn.execute.return_value = _cursor(fetchone=None)
        insert_conn = AsyncMock()
        insert_conn.execute.return_value = _cursor()

        with patch("gw2_progression.services.v5_learning.using_db", side_effect=[_db_context(select_conn), _db_context(insert_conn)]):
            model = await get_user_model("New.Player")

        assert model["account_name"] == "New.Player"
        assert model["total_experiences"] == 0
        assert model["gold_weight"] == 0.3

    @pytest.mark.asyncio
    async def test_personalized_weights_default(self):
        from gw2_progression.services.v5_learning import get_personalized_weights

        select_conn = AsyncMock()
        select_conn.execute.return_value = _cursor(fetchone=None)
        insert_conn = AsyncMock()
        insert_conn.execute.return_value = _cursor()

        with patch("gw2_progression.services.v5_learning.using_db", side_effect=[_db_context(select_conn), _db_context(insert_conn)]):
            weights = await get_personalized_weights("Empty.Player")

        assert abs(weights["gold_weight"] - 0.3) < 0.01


class TestV5API:
    def _ok(self, code):
        return code in (200, 429)

    def test_model_endpoint(self):
        from fastapi.testclient import TestClient

        from gw2_progression.api.main import app

        client = TestClient(app)
        resp = client.get("/v5/model/Test.Player")
        assert self._ok(resp.status_code)

    def test_weights_endpoint(self):
        from fastapi.testclient import TestClient

        from gw2_progression.api.main import app

        client = TestClient(app)
        resp = client.get("/v5/weights/Test.Player")
        assert self._ok(resp.status_code)

    def test_experience_endpoint(self):
        from fastapi.testclient import TestClient

        from gw2_progression.api.main import app

        client = TestClient(app)
        resp = client.get("/v5/experiences/Test.Player")
        assert self._ok(resp.status_code)
