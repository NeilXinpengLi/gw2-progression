from fastapi.testclient import TestClient

from gw2_progression.api.main import app
from gw2_progression.lifecycle.core.backward.dependency_solver import Dependency, DependencySolver
from gw2_progression.lifecycle.core.backward.hypothesis_generator import Hypothesis, HypothesisGenerator
from gw2_progression.lifecycle.core.backward.inference_engine import BackwardInferenceEngine, InferredPath
from gw2_progression.lifecycle.core.engine import LifecycleEngine
from gw2_progression.lifecycle.core.forward.oosk_simulator import OOSKSimulator
from gw2_progression.lifecycle.core.forward.state_evolver import StateEvolver
from gw2_progression.lifecycle.core.rules.crafting_rules import CraftingRules
from gw2_progression.lifecycle.core.rules.dgsk_constraints import DGSKConstraints
from gw2_progression.lifecycle.core.rules.economy_rules import EconomyRules
from gw2_progression.lifecycle.core.trajectory.path_generator import TrajectoryGenerator
from gw2_progression.lifecycle.core.trajectory.path_ranker import PathRanker
from gw2_progression.lifecycle.core.validation.consistency_checker import ConsistencyChecker
from gw2_progression.lifecycle.core.validation.simulation_validator import SimulationValidator

# ── Sample test data ─────────────────────────────────────────────────────

SAMPLE_STATE = {
    "inventory": {"mystic_coin": 10, "ectoplasm": 5, "damask": 3},
    "market": {
        "mystic_coin": {"price": 100, "supply": 500, "demand": 450, "velocity": 1.2},
        "ectoplasm": {"price": 80, "supply": 300, "demand": 350, "velocity": 1.5},
        "damask": {"price": 200, "supply": 100, "demand": 150, "velocity": 1.8},
    },
    "achievements": ["world_completion"],
    "gold": 5000,
}

SAMPLE_ACTIONS = [
    {"type": "farm", "item_id": "magnetite_shard", "quantity": 3},
    {"type": "trade", "item_id": "mystic_coin", "quantity": 5},
    {"type": "craft", "item_id": "legendary_component", "consumes": {"mystic_coin": 1}},
]


# ── Backward Inference ────────────────────────────────────────────────────

class TestInferredPath:
    def test_creation(self):
        p = InferredPath(steps=SAMPLE_ACTIONS, probability=0.8)
        assert len(p.steps) == 3
        assert p.probability == 0.8

    def test_copy(self):
        p1 = InferredPath(steps=SAMPLE_ACTIONS, probability=0.9)
        p2 = p1.copy()
        assert p2.probability == 0.9
        assert p2.steps == p1.steps
        p2.steps.append({"type": "skip"})
        assert len(p1.steps) != len(p2.steps)


class TestBackwardInferenceEngine:
    def test_infer_history(self):
        engine = BackwardInferenceEngine()
        paths = engine.infer_history(SAMPLE_STATE, max_depth=5)
        assert len(paths) >= 1

    def test_infer_history_with_rules(self):
        engine = BackwardInferenceEngine()
        paths = engine.infer_history_with_rules(SAMPLE_STATE, [], max_depth=5)
        assert len(paths) == 0

    def test_apply_reverse_rule_none(self):
        engine = BackwardInferenceEngine()
        result = engine.apply_reverse_rule(None, SAMPLE_STATE)
        assert result is None

    def test_rank_orders_by_probability(self):
        engine = BackwardInferenceEngine()
        paths = [
            InferredPath(steps=[], probability=0.3, rule_consistency=0.8, economy_likelihood=0.7),
            InferredPath(steps=[], probability=0.9, rule_consistency=0.8, economy_likelihood=0.7),
            InferredPath(steps=[], probability=0.5, rule_consistency=0.8, economy_likelihood=0.7),
        ]
        ranked = engine._rank(paths)
        assert ranked[0].probability == 0.9
        assert ranked[-1].probability == 0.3


# ── Dependency Solver ─────────────────────────────────────────────────────

class TestDependency:
    def test_creation(self):
        d = Dependency(entity_id="legendary_weapon", entity_type="crafting")
        assert d.entity_id == "legendary_weapon"
        assert d.resolved is False

    def test_to_dict(self):
        d = Dependency(entity_id="test", entity_type="item", requires=["a", "b"])
        dd = d.to_dict()
        assert dd["entity_id"] == "test"
        assert dd["requires"] == ["a", "b"]


class TestDependencySolver:
    def test_register(self):
        solver = DependencySolver()
        solver.register("item:1", "material")
        assert "item:1" in solver.dependencies

    def test_register_with_requires(self):
        solver = DependencySolver()
        solver.register("item:1", "crafting", requires=["mat:1", "mat:2"])
        assert solver.dependencies["mat:1"].required_by == ["item:1"]

    def test_resolve_chain(self):
        solver = DependencySolver()
        solver.register("legendary", "crafting", requires=["gift"])
        solver.register("gift", "currency", requires=["coin"])
        solver.register("coin", "material")
        chain = solver.resolve("legendary")
        assert len(chain) >= 2

    def test_resolve_unknown(self):
        solver = DependencySolver()
        chain = solver.resolve("nonexistent")
        assert chain == []

    def test_has_dependency(self):
        solver = DependencySolver()
        solver.register("item", "crafting", requires=["mat"])
        assert solver.has_dependency("item") is True
        assert solver.has_dependency("mat") is False

    def test_register_account_dependencies(self):
        solver = DependencySolver()
        solver.register_account_dependencies()
        assert "legendary_weapon" in solver.dependencies
        assert "gift_of_mastery" in solver.dependencies

    def test_to_dict(self):
        solver = DependencySolver()
        solver.register("a", "type_a")
        d = solver.to_dict()
        assert "a" in d


# ── Hypothesis Generator ──────────────────────────────────────────────────

class TestHypothesis:
    def test_creation(self):
        h = Hypothesis(steps=SAMPLE_ACTIONS, probability=0.7)
        assert len(h.steps) == 3
        assert h.probability == 0.7


class TestHypothesisGenerator:
    def test_generate(self):
        gen = HypothesisGenerator()
        hypotheses = gen.generate(SAMPLE_STATE, max_depth=5, count=3)
        assert len(hypotheses) >= 1

    def test_generate_for_item(self):
        gen = HypothesisGenerator()
        hypotheses = gen.generate_for_item("legendary_weapon", SAMPLE_STATE)
        assert len(hypotheses) >= 1

    def test_generate_for_unknown_item(self):
        gen = HypothesisGenerator()
        state = {"items": [], "inventory": {}, "achievements": []}
        hypotheses = gen.generate_for_item("nonexistent", state)
        assert len(hypotheses) >= 0


# ── State Evolver ─────────────────────────────────────────────────────────

class TestStateEvolver:
    def test_evolve_farm(self):
        evolver = StateEvolver()
        state = {"inventory": {}, "market": {"ore": {"supply": 100, "demand": 100, "price": 50}}}
        result = evolver.evolve(state, {"type": "farm", "item_id": "ore", "quantity": 5})
        assert result["inventory"].get("ore") == 5
        assert result["time"] == 1

    def test_evolve_trade(self):
        evolver = StateEvolver()
        state = {"inventory": {}, "market": {"coin": {"supply": 100, "demand": 100, "price": 100}}}
        result = evolver.evolve(state, {"type": "trade", "item_id": "coin", "quantity": 3})
        assert result["inventory"].get("coin") == 3

    def test_evolve_craft(self):
        evolver = StateEvolver()
        state = {"inventory": {"mystic_coin": 2}, "market": {"component": {"supply": 0, "demand": 0, "price": 500}}}
        result = evolver.evolve(state, {"type": "craft", "item_id": "component", "consumes": {"mystic_coin": 1}})
        assert result["inventory"].get("component") == 1
        assert result["inventory"].get("mystic_coin") == 1

    def test_evolve_achievement(self):
        evolver = StateEvolver()
        state = {"inventory": {}, "achievements": []}
        result = evolver.evolve(state, {"type": "achievement", "item_id": "world_completion", "progress": 100})
        assert "world_completion" in result.get("achievements", [])

    def test_evolve_multi(self):
        evolver = StateEvolver()
        state = {"inventory": {}, "time": 0}
        actions = [
            {"type": "farm", "item_id": "ore", "quantity": 1},
            {"type": "farm", "item_id": "ore", "quantity": 2},
        ]
        trajectory = evolver.evolve_multi(state, actions)
        assert len(trajectory) == 3
        assert trajectory[-1]["inventory"]["ore"] == 3


# ── OOSK Simulator ────────────────────────────────────────────────────────

class TestOOSKSimulator:
    def test_simulate(self):
        sim = OOSKSimulator()
        state = {"inventory": {"mystic_coin": 2}, "market": {"mystic_coin": {"price": 100, "supply": 100, "demand": 100}}}
        trajectory = sim.simulate(state, steps=3)
        assert len(trajectory) >= 1
        assert len(trajectory) <= 4

    def test_simulate_with_actions(self):
        sim = OOSKSimulator()
        state = {"inventory": {}, "market": {}}
        trajectory = sim.simulate_with_actions(state, SAMPLE_ACTIONS)
        assert len(trajectory) == 4

    def test_simulate_branching(self):
        sim = OOSKSimulator()
        state = {"inventory": {}, "market": {}}
        branches = sim.simulate_branching(state, steps=3, branches=2)
        assert len(branches) == 2

    def test_empty_state(self):
        sim = OOSKSimulator()
        trajectory = sim.simulate({}, steps=2)
        assert len(trajectory) >= 1


# ── Crafting Rules ────────────────────────────────────────────────────────

class TestCraftingRules:
    def test_can_craft(self):
        rules = CraftingRules()
        result = rules.can_craft({"mystic_coin": 1, "ectoplasm": 2}, "legendary_component")
        assert result is True

    def test_cannot_craft(self):
        rules = CraftingRules()
        result = rules.can_craft({}, "legendary_component")
        assert result is False

    def test_craft_success(self):
        rules = CraftingRules()
        inv = {"mystic_coin": 2, "ectoplasm": 3}
        result = rules.craft(inv, "legendary_component")
        assert result["success"] is True
        assert result["output"] == "legendary_component"

    def test_craft_failure(self):
        rules = CraftingRules()
        result = rules.craft({}, "nonexistent")
        assert result["success"] is False

    def test_craft_missing_ingredients(self):
        rules = CraftingRules()
        result = rules.craft({}, "legendary_component")
        assert result["success"] is False

    def test_reverse_craft(self):
        rules = CraftingRules()
        result = rules.reverse_craft("legendary_component")
        assert result is not None
        assert "ingredients" in result

    def test_reverse_craft_unknown(self):
        rules = CraftingRules()
        result = rules.reverse_craft("nonexistent")
        assert result is None

    def test_get_crafting_chain(self):
        rules = CraftingRules()
        chain = rules.get_crafting_chain("legendary_component")
        assert len(chain) >= 1

    def test_validate_crafting_state(self):
        rules = CraftingRules()
        result = rules.validate_crafting_state({"inventory": {}})
        assert isinstance(result, dict)
        assert "valid" in result


# ── Economy Rules ─────────────────────────────────────────────────────────

class TestEconomyRules:
    def test_validate_price_valid(self):
        rules = EconomyRules()
        result = rules.validate_price("coin", 100.0)
        assert result["valid"] is True

    def test_validate_price_below_floor(self):
        rules = EconomyRules(price_floor=5.0)
        result = rules.validate_price("coin", 1.0)
        assert result["valid"] is False

    def test_validate_trade_valid(self):
        rules = EconomyRules()
        result = rules.validate_trade(100, 120, 5)
        assert result["valid"] is True

    def test_validate_trade_invalid_prices(self):
        rules = EconomyRules()
        result = rules.validate_trade(0, 0, 1)
        assert result["valid"] is False

    def test_validate_trade_no_spread(self):
        rules = EconomyRules()
        result = rules.validate_trade(100, 100, 1)
        assert result["valid"] is False

    def test_validate_economy_state(self):
        rules = EconomyRules()
        state = {"market": {"coin": {"supply": 100, "demand": 120, "price": 100, "velocity": 1.0}}}
        result = rules.validate_economy_state(state)
        assert result["valid"] is True

    def test_is_market_stable(self):
        rules = EconomyRules()
        market = {"a": {"velocity": 1.0}, "b": {"velocity": 0.5}}
        assert rules.is_market_stable(market) is True


# ── DGSK Constraints ──────────────────────────────────────────────────────

class TestDGSKConstraints:
    def test_validate_valid_state(self):
        c = DGSKConstraints()
        state = {"inventory": {"mystic_coin": 1}, "market": {"coin": {"price": 100, "supply": 50, "demand": 60}}}
        assert c.validate(state) is True

    def test_validate_invalid_inventory(self):
        c = DGSKConstraints()
        state = {"inventory": {"item": -1}, "market": {}}
        assert c.validate(state) is False

    def test_validate_detailed(self):
        c = DGSKConstraints()
        state = {"inventory": {}, "market": {}}
        result = c.validate_detailed(state)
        assert "valid" in result
        assert "crafting" in result
        assert "economy" in result

    def test_is_terminal(self):
        c = DGSKConstraints()
        state = {"inventory": {"goal_item": 1}, "goal_items": ["goal_item"]}
        assert c.is_terminal(state) is True

    def test_is_not_terminal(self):
        c = DGSKConstraints()
        state = {"inventory": {}, "goal_items": ["goal_item"]}
        assert c.is_terminal(state) is False


# ── Trajectory Generator ──────────────────────────────────────────────────

class TestTrajectoryGenerator:
    def test_generate(self):
        gen = TrajectoryGenerator()
        paths = gen.generate(SAMPLE_STATE, max_depth=3)
        assert len(paths) >= 0

    def test_generate_counterfactual(self):
        gen = TrajectoryGenerator()
        paths = gen.generate_counterfactual(SAMPLE_STATE, {"type": "skip"}, step_index=0)
        assert len(paths) >= 0


# ── Path Ranker ──────────────────────────────────────────────────────────

class TestPathRanker:
    def test_rank(self):
        ranker = PathRanker()
        paths = [
            InferredPath(steps=SAMPLE_ACTIONS, probability=0.9, rule_consistency=0.8, economy_likelihood=0.7),
            InferredPath(steps=SAMPLE_ACTIONS, probability=0.5, rule_consistency=0.8, economy_likelihood=0.7),
        ]
        ranked = ranker.rank(paths)
        assert len(ranked) == 2
        assert ranked[0].probability == 0.9

    def test_get_top_k(self):
        ranker = PathRanker()
        paths = [InferredPath(steps=[], probability=i * 0.25, rule_consistency=0.8, economy_likelihood=0.7) for i in range(4)]
        top = ranker.get_top_k(paths, k=2)
        assert len(top) == 2

    def test_get_alternatives(self):
        ranker = PathRanker()
        paths = [InferredPath(steps=[], probability=i * 0.25, rule_consistency=0.8, economy_likelihood=0.7) for i in range(4)]
        alts = ranker.get_alternatives(paths, top_n=2)
        assert len(alts) >= 1
        assert alts[0].probability < paths[-1].probability


# ── Consistency Checker ───────────────────────────────────────────────────

class TestConsistencyChecker:
    def test_validate_exact_match(self):
        c = ConsistencyChecker(tolerance=0.0)
        state = {"inventory": {"coin": 1}, "market": {}}
        assert c.validate(state, state) is True

    def test_validate_no_match(self):
        c = ConsistencyChecker(tolerance=0.0)
        a = {"inventory": {"coin": 1}, "market": {}}
        b = {"inventory": {"coin": 999}, "market": {}}
        assert c.validate(a, b) is False

    def test_match_ratio(self):
        c = ConsistencyChecker()
        a = {"inventory": {"coin": 1, "ore": 2}, "market": {"x": {"price": 100}}}
        b = {"inventory": {"coin": 1, "ore": 5}, "market": {"x": {"price": 100}}}
        ratio = c.match_ratio(a, b)
        assert ratio > 0

    def test_validate_trajectory(self):
        c = ConsistencyChecker()
        traj = [{"inventory": {"coin": 0}}, {"inventory": {"coin": 5}}]
        final = {"inventory": {"coin": 5}}
        score = c.validate_trajectory(traj, final)
        assert score >= 0


# ── Simulation Validator ──────────────────────────────────────────────────

class TestSimulationValidator:
    def test_validate_path(self):
        v = SimulationValidator()
        path = InferredPath(steps=SAMPLE_ACTIONS, start_state=SAMPLE_STATE)
        result = v.validate_path(path, SAMPLE_STATE)
        assert "valid" in result
        assert "constraint_compliance" in result
        assert "consistency_score" in result

    def test_validate_state(self):
        v = SimulationValidator()
        result = v.validate_state(SAMPLE_STATE)
        assert "valid" in result

    def test_simulate_and_validate(self):
        v = SimulationValidator()
        result = v.simulate_and_validate(SAMPLE_STATE, steps=3)
        assert "trajectory_length" in result
        assert "steps" in result


# ── Lifecycle Engine ──────────────────────────────────────────────────────

class TestLifecycleEngine:
    def test_reconstruct(self):
        engine = LifecycleEngine()
        result = engine.reconstruct(SAMPLE_STATE, max_depth=3)
        assert "paths" in result
        assert "state_snapshot" in result
        assert "total_paths" in result

    def test_reconstruct_empty_state(self):
        engine = LifecycleEngine()
        result = engine.reconstruct({}, max_depth=2)
        assert "paths" in result

    def test_reconstruct_item(self):
        engine = LifecycleEngine()
        result = engine.reconstruct_item("legendary_weapon", SAMPLE_STATE)
        assert "paths" in result

    def test_simulate_forward(self):
        engine = LifecycleEngine()
        result = engine.simulate_forward(SAMPLE_STATE, steps=3)
        assert "trajectory" in result
        assert "end_state" in result

    def test_validate_state(self):
        engine = LifecycleEngine()
        result = engine.validate_state(SAMPLE_STATE)
        assert "valid" in result

    def test_check_crafting_valid(self):
        engine = LifecycleEngine()
        result = engine.check_crafting({"mystic_coin": 2, "ectoplasm": 3}, "legendary_component")
        assert result["success"] is True

    def test_check_crafting_invalid(self):
        engine = LifecycleEngine()
        result = engine.check_crafting({}, "legendary_component")
        assert result["success"] is False

    def test_get_crafting_chain(self):
        engine = LifecycleEngine()
        chain = engine.get_crafting_chain("legendary_component")
        assert len(chain) >= 1

    def test_check_economy(self):
        engine = LifecycleEngine()
        market = {"coin": {"supply": 100, "demand": 120, "price": 100, "velocity": 1.0}}
        result = engine.check_economy(market)
        assert result["valid"] is True

    def test_counterfactual(self):
        engine = LifecycleEngine()
        result = engine.counterfactual(SAMPLE_STATE, {"type": "skip"}, step_index=0)
        assert "paths" in result

    def test_generate_report(self):
        engine = LifecycleEngine()
        result = engine.generate_report(SAMPLE_STATE)
        assert "lifecycle_summary" in result
        assert "state_validation" in result
        assert "most_likely_path" in result or result["trajectory_count"] == 0


# ── Lifecycle API ─────────────────────────────────────────────────────────

class TestLifecycleAPI:
    def test_reconstruct_api(self):
        with TestClient(app) as client:
            resp = client.post("/lifecycle/reconstruct", json={"state": SAMPLE_STATE, "max_depth": 3})
            assert resp.status_code == 200
            data = resp.json()
            assert "paths" in data

    def test_reconstruct_item_api(self):
        with TestClient(app) as client:
            resp = client.post("/lifecycle/reconstruct/item", json={"item_id": "legendary_weapon", "state": SAMPLE_STATE})
            assert resp.status_code == 200

    def test_simulate_api(self):
        with TestClient(app) as client:
            resp = client.post("/lifecycle/simulate", json={"state": SAMPLE_STATE, "steps": 3})
            assert resp.status_code == 200
            data = resp.json()
            assert "trajectory" in data

    def test_validate_api(self):
        with TestClient(app) as client:
            resp = client.post("/lifecycle/validate", json={"state": SAMPLE_STATE})
            assert resp.status_code == 200

    def test_crafting_check_api(self):
        with TestClient(app) as client:
            resp = client.post("/lifecycle/crafting/check", json={"inventory": {"mystic_coin": 2, "ectoplasm": 3}, "recipe_id": "legendary_component"})
            assert resp.status_code == 200

    def test_crafting_chain_api(self):
        with TestClient(app) as client:
            resp = client.post("/lifecycle/crafting/chain", json={"target_item": "legendary_component"})
            assert resp.status_code == 200

    def test_economy_check_api(self):
        with TestClient(app) as client:
            resp = client.post("/lifecycle/economy/check", json={"market": {"coin": {"supply": 100, "demand": 120, "price": 100, "velocity": 1.0}}})
            assert resp.status_code == 200

    def test_counterfactual_api(self):
        with TestClient(app) as client:
            resp = client.post("/lifecycle/counterfactual", json={"state": SAMPLE_STATE, "altered_action": {"type": "skip"}, "step_index": 0})
            assert resp.status_code == 200

    def test_report_api(self):
        with TestClient(app) as client:
            resp = client.post("/lifecycle/report", json={"state": SAMPLE_STATE})
            assert resp.status_code == 200
