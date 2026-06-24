"""Tests for the decision engine and engine routes."""

import pytest


class TestDecisionEngine:
    @pytest.mark.asyncio
    async def test_decide_returns_p0_p1_p2(self):
        from gw2_progression.services.decision_engine import decide

        result = await decide(
            account_name="Test.Player",
            wallet_gold=500000,
            characters=[{"name": "War", "profession": "Warrior", "level": 80}],
            goals=[],
            builds=[{"build_id": "test", "build_name": "Test Build", "readiness_score": 0.85, "missing_items_count": 5}],
            value_data={"total_value_buy": 2000000},
        )

        assert "p0" in result
        assert "p1" in result
        assert "p2" in result
        assert len(result["p0"]) > 0  # At least one P0 action

    @pytest.mark.asyncio
    async def test_decide_no_data(self):
        from gw2_progression.services.decision_engine import decide

        result = await decide(account_name="Empty.Player", wallet_gold=50000)
        assert result["p0"] == []
        assert result["p1"] == []  # No P1 with wallet gold > 0
        assert result["p2"] != []  # Always has default P2 actions

    @pytest.mark.asyncio
    async def test_decide_with_goals(self):
        from gw2_progression.services.decision_engine import decide

        result = await decide(
            account_name="Test.Player",
            goals=[{"name": "Bolt", "progress": 80}],
        )
        p0_names = [a["action"] for a in result["p0"]]
        assert "Complete Legendary" in p0_names

    @pytest.mark.asyncio
    async def test_generate_plan_returns_7_days(self):
        from gw2_progression.services.decision_engine import generate_plan

        result = await generate_plan()
        assert "plan" in result
        assert result["total_days"] == 7
        assert len(result["plan"]) == 7

    @pytest.mark.asyncio
    async def test_generate_plan_with_builds(self):
        from gw2_progression.services.decision_engine import generate_plan

        result = await generate_plan(
            goals=[{"name": "Bolt", "progress": 80}],
            builds=[{"build_id": "b1", "build_name": "Condi Necro", "readiness_score": 0.9}],
        )
        day3_tasks = result["plan"][2]["tasks"]
        assert any("Condi Necro" in t for t in day3_tasks)


class TestEngineAPI:
    def test_engine_decide_requires_key(self):
        from fastapi.testclient import TestClient

        from gw2_progression.api.main import app

        client = TestClient(app)
        resp = client.post("/engine/decide", json={})
        assert resp.status_code == 422

    def test_engine_plan_requires_key(self):
        from fastapi.testclient import TestClient

        from gw2_progression.api.main import app

        client = TestClient(app)
        resp = client.post("/engine/plan", json={})
        assert resp.status_code == 422
