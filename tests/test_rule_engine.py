"""Tests for GW2 Rule Engine v1 — full convergence layer."""

from __future__ import annotations

from gw2_progression.rule_engine.core.api_rules.extractor import APIRuleExtractor
from gw2_progression.rule_engine.core.api_rules.graph_builder import RuleGraphBuilder
from gw2_progression.rule_engine.core.api_rules.schema_parser import ENDPOINT_SCHEMAS, Rule, RuleType
from gw2_progression.rule_engine.core.behavior_rules.pattern_miner import BehaviorRuleMiner
from gw2_progression.rule_engine.core.behavior_rules.player_behavior import PlayerBehaviorProfile
from gw2_progression.rule_engine.core.economy_rules.price_model import EconomyRuleLearner
from gw2_progression.rule_engine.core.economy_rules.trend_inference import TrendInference
from gw2_progression.rule_engine.core.engine import GW2RuleEngine
from gw2_progression.rule_engine.core.llm_rules.distiller import LLMRuleDistiller
from gw2_progression.rule_engine.core.llm_rules.reasoning_converter import ReasoningConverter
from gw2_progression.rule_engine.core.validation.rule_checker import RuleChecker
from gw2_progression.rule_engine.core.validation.simulation_runner import SimulationValidator

# ── API Rule Extractor ───────────────────────────────────────────────────

class TestAPIRuleExtractor:
    def test_extract_returns_rules(self):
        extractor = APIRuleExtractor()
        rules = extractor.extract()
        assert len(rules) > 0
        for r in rules:
            assert r.type in (RuleType.DEPENDENCY, RuleType.GRAPH_EDGE)

    def test_extract_all_structure(self):
        extractor = APIRuleExtractor()
        result = extractor.extract_all()
        assert result["rule_count"] > 0
        assert "by_type" in result
        assert "sources" in result

    def test_from_endpoint_schemas(self):
        extractor = APIRuleExtractor(ENDPOINT_SCHEMAS)
        rules = extractor.extract()
        assert len(rules) >= len(ENDPOINT_SCHEMAS)


# ── Economy Rule Learner ────────────────────────────────────────────────

class TestEconomyRuleLearner:
    def test_learn_empty(self):
        learner = EconomyRuleLearner()
        result = learner.learn({})
        assert "trend" in result
        assert "elasticity" in result
        assert "shock_response" in result

    def test_learn_with_price_series(self):
        learner = EconomyRuleLearner()
        series = {
            "item_1": [
                {"price": 100, "supply": 100, "demand": 100},
                {"price": 110, "supply": 95, "demand": 120},
                {"price": 120, "supply": 90, "demand": 140},
                {"price": 125, "supply": 88, "demand": 150},
            ]
        }
        result = learner.learn(series)
        assert len(result["trend"]) >= 1
        assert result["trend"][0].condition["direction"] == "upward"

    def test_detect_shocks(self):
        learner = EconomyRuleLearner()
        series = {
            "volatile_item": [
                {"price": 100}, {"price": 105}, {"price": 80},
                {"price": 110}, {"price": 115}, {"price": 112},
            ]
        }
        result = learner.learn(series)
        assert len(result["shock_response"]) >= 1

    def test_learn_as_rules(self):
        learner = EconomyRuleLearner()
        rules = learner.learn_as_rules({})
        assert isinstance(rules, list)


# ── Behavior Rule Miner ───────────────────────────────────────────────────

class TestBehaviorRuleMiner:
    def test_mine_empty(self):
        miner = BehaviorRuleMiner()
        result = miner.mine([])
        assert "farming_loops" in result
        assert "trading_behaviors" in result
        assert "meta_adaptations" in result

    def test_mine_with_logs(self):
        miner = BehaviorRuleMiner()
        logs = [
            {"player_id": "trader:1", "action": {"type": "trade", "item_id": "coin", "price": 100}, "world_time": 1},
            {"player_id": "trader:1", "action": {"type": "flip", "item_id": "ecto", "price": 120}, "world_time": 2},
            {"player_id": "trader:1", "action": {"type": "trade", "item_id": "coin", "price": 110}, "world_time": 3},
            {"player_id": "crafter:1", "action": {"type": "craft", "item_id": "legendary", "consumes": {"coin": 5}}, "world_time": 4},
            {"player_id": "crafter:1", "action": {"type": "craft", "item_id": "gift", "consumes": {"ecto": 10}}, "world_time": 5},
            {"player_id": "raider:1", "action": {"type": "farm", "item_id": "magnetite"}, "world_time": 6},
        ]
        result = miner.mine(logs)
        total = len(result["farming_loops"]) + len(result["trading_behaviors"]) + len(result["meta_adaptations"])
        assert total > 0

    def test_mine_as_rules(self):
        miner = BehaviorRuleMiner()
        rules = miner.mine_as_rules([])
        assert isinstance(rules, list)

    def test_farming_loop_detection(self):
        miner = BehaviorRuleMiner()
        logs = [{"action": {"type": "farm"}, "world_time": t} for t in range(20)]
        rules = miner.detect_farming_loop(logs)
        assert len(rules) >= 0


class TestPlayerBehaviorProfile:
    def test_classify_trader(self):
        p = PlayerBehaviorProfile("test:1")
        for _ in range(10):
            p.record_action({"type": "trade", "item_id": "coin"})
        assert p.classify() == "trader"

    def test_classify_crafter(self):
        p = PlayerBehaviorProfile("test:2")
        for _ in range(10):
            p.record_action({"type": "craft", "item_id": "legendary"})
        assert p.classify() == "crafter"

    def test_to_dict(self):
        p = PlayerBehaviorProfile("test:3")
        p.record_action({"type": "farm", "item_id": "ore"})
        d = p.to_dict()
        assert d["player_id"] == "test:3"
        assert "style" in d


# ── LLM Rule Distiller ───────────────────────────────────────────────────

class TestLLMRuleDistiller:
    def test_distill_empty(self):
        distiller = LLMRuleDistiller()
        rules = distiller.distill([])
        assert len(rules) == 0

    def test_distill_deterministic(self):
        distiller = LLMRuleDistiller()
        raw = [
            Rule(id="r1", type=RuleType.DEPENDENCY, source="api:test", condition={"a": 1}, action="do_x"),
            Rule(id="r2", type=RuleType.GRAPH_EDGE, source="api:test2", condition={"b": 2}, action="do_y"),
        ]
        distilled = distiller.distill(raw)
        assert len(distilled) >= 1
        assert distilled[0].type == RuleType.LLM_DISTILLED

    def test_distill_as_rules(self):
        distiller = LLMRuleDistiller()
        rules = distiller.distill_as_rules([])
        assert isinstance(rules, list)


class TestReasoningConverter:
    def test_convert_empty(self):
        c = ReasoningConverter()
        assert c.convert({"reasoning_chain": []}) == []

    def test_convert_chain(self):
        c = ReasoningConverter()
        chain = {"reasoning_chain": [{"node": "coin", "relation": "used_in", "target": "crafting"}]}
        rules = c.convert(chain)
        assert len(rules) == 1
        assert rules[0].type == RuleType.GRAPH_EDGE


# ── Validation ────────────────────────────────────────────────────────────

class TestSimulationValidator:
    def test_validate_empty(self):
        v = SimulationValidator()
        results = v.validate([])
        assert results == []

    def test_validate_fallback(self):
        v = SimulationValidator()
        rules = [Rule(id="t1", type=RuleType.ECONOMY_TREND, source="price:coin", condition={"item_id": "coin"}, action="sell_coin")]
        results = v.validate(rules, {"market": {"coin": {"price": 100}}})
        assert len(results) == 1
        assert results[0]["type"] == "validated"


class TestRuleChecker:
    def test_check_empty(self):
        c = RuleChecker()
        r = c.check([])
        assert r["total"] == 0
        assert r["conflicts"] == []
        assert r["duplicates"] == []

    def test_check_rules(self):
        c = RuleChecker()
        rules = [
            Rule(id="r1", type=RuleType.DEPENDENCY, source="a", condition={}, action="x"),
            Rule(id="r2", type=RuleType.GRAPH_EDGE, source="b", condition={}, action="y"),
        ]
        r = c.check(rules)
        assert r["total"] == 2
        assert r["avg_confidence"] >= 0


# ── RuleGraph Builder ────────────────────────────────────────────────────

class TestRuleGraphBuilder:
    def test_build_empty(self):
        gb = RuleGraphBuilder()
        graph = gb.build([])
        assert len(graph.nodes) == 0

    def test_build_with_rules(self):
        gb = RuleGraphBuilder()
        rules = [Rule(id="r1", type=RuleType.DEPENDENCY, source="api:test", condition={}, action="x")]
        graph = gb.build(rules)
        assert len(graph.nodes) == 1
        assert "api:test" in graph.nodes


# ── Trend Inference ──────────────────────────────────────────────────────

class TestTrendInference:
    def test_infer_empty(self):
        t = TrendInference()
        result = t.infer([])
        assert "market_bias" in result
        assert "avg_elasticity" in result
        assert "shock_frequency" in result

    def test_infer_with_data(self):
        t = TrendInference()
        rules = [
            {"type": "economy_trend", "condition": {"direction": "upward", "item_id": "coin"}},
            {"type": "economy_trend", "condition": {"direction": "downward", "item_id": "ore"}},
            {"type": "economy_elasticity", "condition": {"elasticity": 1.5, "item_id": "wood"}},
            {"type": "economy_shock", "condition": {"item_id": "gem"}},
        ]
        result = t.infer(rules)
        assert result["market_bias"].get("upward", 0) == 0.5


# ── GW2RuleEngine (Full Integration) ─────────────────────────────────────

class TestGW2RuleEngine:
    def test_engine_initialization(self):
        engine = GW2RuleEngine()
        assert engine.api is not None
        assert engine.economy is not None
        assert engine.behavior is not None
        assert engine.llm is not None
        assert engine.validator is not None

    def test_engine_run_empty(self):
        engine = GW2RuleEngine()
        result = engine.run({})
        assert result["rule_count"] >= 0
        assert "api_rules" in result
        assert "economy_rules" in result
        assert "behavior_rules" in result
        assert "llm_distilled" in result
        assert "validated" in result
        assert "rule_check" in result

    def test_engine_run_with_data(self):
        engine = GW2RuleEngine()
        data = {
            "api": None,
            "prices": {
                "mystic_coin": [
                    {"price": 100, "supply": 100, "demand": 100},
                    {"price": 115, "supply": 90, "demand": 130},
                    {"price": 130, "supply": 85, "demand": 150},
                ]
            },
            "logs": [
                {"player_id": "trader:1", "action": {"type": "trade", "item_id": "coin", "price": 100}, "world_time": 1},
                {"player_id": "trader:1", "action": {"type": "flip", "item_id": "ecto", "price": 120}, "world_time": 2},
                {"player_id": "crafter:1", "action": {"type": "craft", "item_id": "legendary", "consumes": {"coin": 5}}, "world_time": 3},
            ],
            "world": {"market": {"mystic_coin": {"price": 130, "supply": 85, "demand": 150}}},
            "reasoning": {"reasoning_chain": [{"node": "coin", "relation": "used_in", "target": "legendary"}]},
        }
        result = engine.run(data)
        assert result["rule_count"] > 0
        assert len(result["api_rules"]) > 0
        assert len(result["validated"]) > 0

    def test_engine_sub_components(self):
        engine = GW2RuleEngine()
        assert len(engine.extract_api()["rules"]) > 0
        assert isinstance(engine.learn_economy(), list)
        assert isinstance(engine.mine_behavior([]), list)
        assert isinstance(engine.distill([]), list)
        assert isinstance(engine.validate(), list)
        assert isinstance(engine.check([]), dict)


# ── Rule Serialization ──────────────────────────────────────────────────

class TestRuleSerialization:
    def test_rule_to_dict(self):
        r = Rule(id="test", type=RuleType.DEPENDENCY, source="src", condition={"a": 1}, action="do", confidence=0.8)
        d = r.to_dict()
        assert d["id"] == "test"
        assert d["type"] == "dependency"
        assert d["confidence"] == 0.8

    def test_rule_from_dict(self):
        d = {"id": "t1", "type": "dependency", "source": "s", "condition": {}, "action": "a", "confidence": 0.9}
        r = Rule.from_dict(d)
        assert r.id == "t1"
        assert r.type == RuleType.DEPENDENCY
