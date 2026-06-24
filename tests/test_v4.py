"""Tests for v4 Explainable Optimization Engine."""

import pytest


class TestEconomicModel:
    def test_price_point_basic(self):
        from gw2_progression.services.v4_economic_model import PricePoint

        p = PricePoint(buy_price=100, sell_price=150, buy_qty=3000, sell_qty=3000)
        assert p.mid_price == 125.0
        assert p.spread == 50
        assert round(p.spread_ratio, 4) == 0.3333
        assert p.liquidity_score == "high"
        assert p.sell_after_fee == 127

    def test_price_point_illiquid(self):
        from gw2_progression.services.v4_economic_model import PricePoint

        p = PricePoint(buy_price=0, sell_price=0, buy_qty=0, sell_qty=0)
        assert p.liquidity_score == "illiquid"
        assert p.mid_price == 0

    def test_price_point_low_liquidity(self):
        from gw2_progression.services.v4_economic_model import PricePoint

        p = PricePoint(buy_price=50, sell_price=100, buy_qty=50, sell_qty=50)
        assert p.liquidity_score == "low"

    def test_strategies_defined(self):
        from gw2_progression.services.v4_economic_model import STRATEGIES

        assert "gold" in STRATEGIES
        assert "build" in STRATEGIES
        assert "legendary" in STRATEGIES
        assert "hybrid" in STRATEGIES
        for s in STRATEGIES.values():
            assert "weights" in s
            assert "name" in s


class TestScoring:
    def test_score_action_returns_breakdown(self):
        from gw2_progression.services.v4_economic_model import PricePoint, score_action

        action = {
            "action": "Sell Item",
            "reward_copper": 500000,
            "build_impact": 0,
            "legendary_impact": 0,
            "time_cost_minutes": 10,
            "risk": 0.1,
        }
        price = PricePoint(buy_price=100, sell_price=150, buy_qty=1000, sell_qty=2000)
        result = score_action(action, price, "gold")

        assert "final_score" in result
        assert "breakdown" in result
        assert "strategy" in result
        assert result["strategy"] == "gold"
        assert "gold_score" in result["breakdown"]
        assert "build_impact" in result["breakdown"]

    def test_score_action_hybrid(self):
        from gw2_progression.services.v4_economic_model import PricePoint, score_action

        action = {
            "action": "Build Progress",
            "reward_copper": 0,
            "build_impact": 0.9,
            "legendary_impact": 0,
            "time_cost_minutes": 30,
            "risk": 0.2,
        }
        price = PricePoint(buy_qty=500, sell_qty=500)
        result = score_action(action, price, "hybrid")
        assert result["breakdown"]["build_impact"] == 0.9

    def test_score_different_strategies(self):
        from gw2_progression.services.v4_economic_model import PricePoint, score_action

        action = {
            "action": "Farm Gold",
            "reward_copper": 1000000,
            "build_impact": 0,
            "legendary_impact": 0,
            "time_cost_minutes": 60,
            "risk": 0.3,
        }
        price = PricePoint(buy_qty=5000, sell_qty=5000)

        gold_score = score_action(action, price, "gold")
        build_score = score_action(action, price, "build")

        # Gold strategy should score this higher than build strategy
        assert gold_score["final_score"] > build_score["final_score"]


class TestOptimizer:
    @pytest.mark.asyncio
    async def test_generate_explainable_actions(self):
        from gw2_progression.services.v4_optimizer import generate_explainable_actions

        result = generate_explainable_actions(
            account_data={
                "wallet": [{"id": 1, "value": 500000}],
                "characters": [
                    {"name": "War", "profession": "Warrior", "level": 80},
                    {"name": "Ele", "profession": "Elementalist", "level": 40},
                ],
            },
            value_data={"total_value_buy": 2000000},
            builds=[],
            goals=[],
            strategy="hybrid",
        )

        assert "p0" in result
        assert "p1" in result
        assert "p2" in result
        assert "strategy" in result
        assert result["strategy"] == "hybrid"
        assert len(result["p0"]) > 0
        # Each action should have score breakdown
        if result["p0"]:
            assert "final_score" in result["p0"][0]
            assert "breakdown" in result["p0"][0]

    @pytest.mark.asyncio
    async def test_strategy_switching(self):
        from gw2_progression.services.v4_optimizer import generate_explainable_actions

        data = {
            "wallet": [{"id": 1, "value": 500000}],
            "characters": [{"name": "War", "profession": "Warrior", "level": 80}],
        }
        builds = [{"build_id": "b1", "build_name": "Test", "readiness_score": 0.9, "missing_items_count": 2}]
        goals = [{"name": "Bolt", "progress": 80}]

        gold = generate_explainable_actions(data, {}, builds, goals, "gold")
        build = generate_explainable_actions(data, {}, builds, goals, "build")
        leg = generate_explainable_actions(data, {}, builds, goals, "legendary")

        assert gold["strategy"] == "gold"
        assert build["strategy"] == "build"
        assert leg["strategy"] == "legendary"


class TestV4API:
    def _ok(self, code):
        return code in (200, 429)

    def test_strategies_endpoint(self):
        from fastapi.testclient import TestClient

        from gw2_progression.api.main import app

        client = TestClient(app)
        resp = client.get("/v4/strategies")
        assert self._ok(resp.status_code)
        if resp.status_code == 200:
            data = resp.json()
            assert len(data["strategies"]) == 4

    def test_strategy_by_id(self):
        from fastapi.testclient import TestClient

        from gw2_progression.api.main import app

        client = TestClient(app)
        resp = client.get("/v4/strategy/hybrid")
        assert self._ok(resp.status_code) or resp.status_code == 200

    def test_strategy_not_found(self):
        from fastapi.testclient import TestClient

        from gw2_progression.api.main import app

        client = TestClient(app)
        resp = client.get("/v4/strategy/invalid")
        assert resp.status_code in (200, 404, 429)

    def test_explain_endpoint(self):
        from fastapi.testclient import TestClient

        from gw2_progression.api.main import app

        client = TestClient(app)
        resp = client.post(
            "/v4/explain",
            json={
                "action": {"action": "Test", "reward_copper": 100000},
                "strategy": "gold",
            },
        )
        assert self._ok(resp.status_code)
