"""Tests for v4 Economic Model — PricePoint, CraftCost, strategy weights, scoring."""

from gw2_progression.services.v4_economic_model import (
    STRATEGIES,
    CraftCost,
    PricePoint,
    score_action,
)


class TestPricePoint:
    def test_zero_prices(self):
        p = PricePoint()
        assert p.mid_price == 0
        assert p.spread == 0
        assert p.spread_ratio == 0
        assert p.liquidity_score == "illiquid"
        assert p.sell_after_fee == 0

    def test_mid_price(self):
        p = PricePoint(buy_price=10000, sell_price=12000)
        assert p.mid_price == 11000
        assert p.spread == 2000

    def test_spread_ratio(self):
        p = PricePoint(buy_price=10000, sell_price=11000)
        assert p.spread_ratio == round(1000 / 11000, 4)

    def test_liquidity_scores(self):
        assert PricePoint(buy_qty=5000, sell_qty=5000).liquidity_score == "high"
        assert PricePoint(buy_qty=300, sell_qty=300).liquidity_score == "medium"
        assert PricePoint(buy_qty=50, sell_qty=0).liquidity_score == "low"
        assert PricePoint(buy_qty=0, sell_qty=0).liquidity_score == "illiquid"

    def test_sell_after_fee(self):
        p = PricePoint(sell_price=10000)
        assert p.sell_after_fee == 8500

    def test_single_price_mid(self):
        p = PricePoint(buy_price=5000, sell_price=0)
        assert p.mid_price == 2500
        p2 = PricePoint(buy_price=0, sell_price=5000)
        assert p2.mid_price == 2500


class TestCraftCost:
    def test_zero_cost(self):
        c = CraftCost()
        assert c.profit_if_craft == 0
        assert c.profit_if_buy == 0
        assert c.craft_margin_pct == 0

    def test_craft_profit(self):
        c = CraftCost(total_craft_cost=50000, sell_price=100000)
        assert c.profit_if_craft == 35000  # 100000*0.85 - 50000
        assert c.craft_margin_pct == round(35000 / 50000 * 100, 1)

    def test_buy_profit(self):
        c = CraftCost(total_buy_cost=60000, sell_price=100000)
        assert c.profit_if_buy == 25000  # 100000*0.85 - 60000

    def test_no_sell_price(self):
        c = CraftCost(total_craft_cost=50000, sell_price=0)
        assert c.profit_if_craft == -50000
        assert c.craft_margin_pct == -100.0


class TestStrategies:
    def test_all_strategies_defined(self):
        assert "gold" in STRATEGIES
        assert "build" in STRATEGIES
        assert "legendary" in STRATEGIES
        assert "hybrid" in STRATEGIES

    def test_gold_strategy_weights(self):
        w = STRATEGIES["gold"]["weights"]
        assert w["gold"] > w["build"]
        assert w["gold"] > w["legendary"]

    def test_build_strategy_weights(self):
        w = STRATEGIES["build"]["weights"]
        assert w["build"] > w["gold"]
        assert w["build"] > w["legendary"]

    def test_legendary_strategy_weights(self):
        w = STRATEGIES["legendary"]["weights"]
        assert w["legendary"] > w["gold"]
        assert w["legendary"] > w["build"]

    def test_hybrid_is_balanced(self):
        w = STRATEGIES["hybrid"]["weights"]
        assert abs(w["gold"] - w["build"]) < 0.01
        assert abs(w["gold"] - w["legendary"]) < 0.01


class TestScoreAction:
    def test_gold_action_high_reward(self):
        """High gold reward with low time cost scores well under gold strategy."""
        result = score_action(
            action={"reward_copper": 5000000, "build_impact": 0, "legendary_impact": 0, "time_cost_minutes": 5, "risk": 0.1},
            price=PricePoint(buy_qty=5000, sell_qty=5000),
            strategy="gold",
        )
        assert result["final_score"] > 0
        assert "gold_score" in result["breakdown"]
        assert "liquidity_bonus" in result["breakdown"]
        assert result["strategy"] == "gold"

    def test_build_action_scores_under_build_strategy(self):
        """High build impact scores best under build strategy."""
        result = score_action(
            action={"reward_copper": 0, "build_impact": 1.0, "legendary_impact": 0, "time_cost_minutes": 30, "risk": 0.1},
            price=PricePoint(),
            strategy="build",
        )
        assert result["final_score"] > 0.5

    def test_legendary_action_under_legendary_strategy(self):
        result = score_action(
            action={"reward_copper": 0, "build_impact": 0, "legendary_impact": 1.0, "time_cost_minutes": 30, "risk": 0.1},
            price=PricePoint(),
            strategy="legendary",
        )
        assert result["final_score"] > 0

    def test_gold_action_scores_low_under_build_strategy(self):
        """Same gold action scores lower under build vs gold strategy."""
        action = {"reward_copper": 5000000, "build_impact": 0, "legendary_impact": 0, "time_cost_minutes": 5, "risk": 0.1}
        gold = score_action(action, price=PricePoint(), strategy="gold")
        build = score_action(action, price=PricePoint(), strategy="build")
        assert gold["final_score"] > build["final_score"]

    def test_time_cost_affects_score(self):
        """Different time costs produce different scores (model has time weight).
        time_cost=0 gives a default 0.5 score; time_cost=10 gives 1-10/120=0.917."""
        action = {"reward_copper": 100000, "build_impact": 0, "legendary_impact": 0, "time_cost_minutes": 10, "risk": 0.5}
        with_time = score_action(action, price=PricePoint(), strategy="gold")
        action["time_cost_minutes"] = 0
        no_time = score_action(action, price=PricePoint(), strategy="gold")
        # time contributes different amounts, so scores must differ
        assert abs(with_time["final_score"] - no_time["final_score"]) > 0.001

    def test_liquidity_bonus(self):
        """High-liquidity items get a bonus over illiquid."""
        action = {"reward_copper": 500000, "build_impact": 0, "legendary_impact": 0, "time_cost_minutes": 10, "risk": 0.1}
        liquid = score_action(action, price=PricePoint(buy_qty=5000, sell_qty=5000), strategy="gold")
        illiquid = score_action(action, price=PricePoint(buy_qty=0, sell_qty=0), strategy="gold")
        assert liquid["final_score"] > illiquid["final_score"]

    def test_different_strategies_different_scores(self):
        action = {"reward_copper": 5000000, "build_impact": 0.5, "legendary_impact": 0.5, "time_cost_minutes": 30, "risk": 0.1}
        gold = score_action(action, price=PricePoint(), strategy="gold")
        build = score_action(action, price=PricePoint(), strategy="build")
        leg = score_action(action, price=PricePoint(), strategy="legendary")
        scores = {gold["final_score"], build["final_score"], leg["final_score"]}
        assert len(scores) >= 2  # at least 2 differ
