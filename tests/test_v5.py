"""Tests for v5 Self-Evolving Learning Engine."""

import pytest


class TestV5Learning:
    @pytest.mark.asyncio
    async def test_record_experience(self):
        from gw2_progression.services.v5_learning import record_experience

        result = await record_experience(
            account_name="Test.Player",
            action_key="sell_mystic_coin",
            action_label="Sell Mystic Coin",
            gold_impact=320000,
            success=True,
        )
        assert "experience_id" in result
        assert "reward" in result
        assert result["reward"] > 0

    @pytest.mark.asyncio
    async def test_get_user_model_default(self):
        from gw2_progression.services.v5_learning import get_user_model

        model = await get_user_model("New.Player")
        assert model["account_name"] == "New.Player"
        assert model["total_experiences"] == 0
        assert model["gold_weight"] == 0.3

    @pytest.mark.asyncio
    async def test_personalized_weights_default(self):
        from gw2_progression.services.v5_learning import get_personalized_weights

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
