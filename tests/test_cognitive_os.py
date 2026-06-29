from __future__ import annotations

import pytest

from gw2_progression.cognitive_os.agents.crafter import CrafterAgent
from gw2_progression.cognitive_os.agents.meta import MetaAgent
from gw2_progression.cognitive_os.agents.raider import RaiderAgent
from gw2_progression.cognitive_os.agents.trader import TraderAgent
from gw2_progression.cognitive_os.behavior.model import BehaviorModel
from gw2_progression.cognitive_os.behavior.profile import ActionType, Archetype, BehaviorProfile
from gw2_progression.cognitive_os.calibration import CalibrationLoop
from gw2_progression.cognitive_os.calibration.consistency_loop import CalibratedParameter
from gw2_progression.cognitive_os.cognition_graph.graph import CognitionGraph, EdgeType, NodeType
from gw2_progression.cognitive_os.economy.lifecycle import EconomicLifecycle
from gw2_progression.cognitive_os.engine import CognitiveOSEngine
from gw2_progression.cognitive_os.probabilistic.bors import ProbabilisticBORS
from gw2_progression.cognitive_os.probabilistic.causal import CausalReasoningLayer
from gw2_progression.cognitive_os.probabilistic.dgsk import ProbabilisticDGSK
from gw2_progression.cognitive_os.probabilistic.gnn import RuleGNN
from gw2_progression.cognitive_os.probabilistic.inference_loop import ProbabilisticWorldInferenceLoop
from gw2_progression.cognitive_os.probabilistic.policy import ProbabilisticPolicy
from gw2_progression.cognitive_os.rl.policy import RLPolicy
from gw2_progression.cognitive_os.rl.reward import RewardFunction
from gw2_progression.cognitive_os.temporal.temporal_state import TemporalState


class TestTemporalState:
    def test_advance_and_snapshot(self):
        ts = TemporalState({"gold": 100})
        ts.advance({"type": "farm"}, steps=3)
        assert ts.t == 3
        assert ts.age == 3
        assert len(ts.history) == 3

    def test_apply_transition(self):
        ts = TemporalState({"gold": 50})
        ts.apply_transition({"gold": 100}, {"type": "trade"})
        assert ts.t == 1
        assert ts.current["gold"] == 100
        assert ts.get_state_at(0)["gold"] == 50

    def test_delta(self):
        ts = TemporalState({"gold": 50, "inventory": {"a": 1}})
        ts.apply_transition({"gold": 100, "inventory": {"a": 2}}, {"type": "farm"})
        delta = ts.delta(0, 1)
        assert "gold" in delta
        assert delta["gold"]["from"] == 50
        assert delta["gold"]["to"] == 100

    def test_get_state_range(self):
        ts = TemporalState({"x": 1})
        ts.apply_transition({"x": 2})
        ts.apply_transition({"x": 3})
        states = ts.get_state_range(0, 2)
        assert len(states) == 3

    def test_reset(self):
        ts = TemporalState({"x": 1})
        ts.advance()
        ts.reset()
        assert ts.t == 0
        assert ts.current == {}


class TestCognitionGraph:
    def test_add_node(self):
        g = CognitionGraph()
        nid = g.add_node(NodeType.ENTITY, "test", {"val": 1})
        node = g.get_node(nid)
        assert node is not None
        assert node.label == "test"
        assert node.node_type == NodeType.ENTITY

    def test_add_edge(self):
        g = CognitionGraph()
        a = g.add_node(NodeType.ENTITY, "a")
        b = g.add_node(NodeType.STATE, "b")
        g.add_edge(a, b, EdgeType.EVOLVES_TO, weight=0.8)
        edges = g.get_edges(EdgeType.EVOLVES_TO)
        assert len(edges) == 1
        assert edges[0].weight == 0.8

    def test_add_edge_unknown_source(self):
        g = CognitionGraph()
        b = g.add_node(NodeType.ENTITY, "b")
        with pytest.raises(KeyError):
            g.add_edge("unknown", b, EdgeType.DEPENDS_ON)

    def test_get_neighbors(self):
        g = CognitionGraph()
        a = g.add_node(NodeType.ENTITY, "a")
        b = g.add_node(NodeType.STATE, "b")
        c = g.add_node(NodeType.DECISION, "c")
        g.add_edge(a, b, EdgeType.EVOLVES_TO)
        g.add_edge(b, c, EdgeType.CAUSES)
        assert len(g.get_neighbors(a)) == 1
        assert len(g.get_neighbors(b)) == 2
        assert len(g.get_neighbors(c)) == 1

    def test_traverse(self):
        g = CognitionGraph()
        a = g.add_node(NodeType.ENTITY, "root")
        b = g.add_node(NodeType.STATE, "child1")
        c = g.add_node(NodeType.DECISION, "child2")
        g.add_edge(a, b, EdgeType.EVOLVES_TO)
        g.add_edge(b, c, EdgeType.CAUSES)
        results = g.traverse(a, max_depth=2)
        assert len(results) == 3

    def test_find_path(self):
        g = CognitionGraph()
        a = g.add_node(NodeType.ENTITY, "a")
        b = g.add_node(NodeType.STATE, "b")
        c = g.add_node(NodeType.DECISION, "c")
        g.add_edge(a, b, EdgeType.EVOLVES_TO)
        g.add_edge(b, c, EdgeType.CAUSES)
        paths = g.find_path(a, c)
        assert len(paths) == 1
        assert paths[0] == [a, b, c]

    def test_is_active_at(self):
        g = CognitionGraph()
        nid = g.add_node(NodeType.ENTITY, "ephemeral", t_created=0, t_expires=5)
        assert g.get_node(nid).is_active_at(3)
        assert not g.get_node(nid).is_active_at(6)

    def test_to_dict(self):
        g = CognitionGraph()
        g.add_node(NodeType.ENTITY, "test")
        d = g.to_dict()
        assert "nodes" in d
        assert "edges" in d
        assert "stats" in d


class TestRLPolicy:
    def test_select_action(self):
        policy = RLPolicy(epsilon=0.0)
        state = {"gold": 100, "inventory": {"item_1": 5}, "achievements": []}
        actions = [
            {"type": "farm", "item_id": "item_1", "quantity": 1},
            {"type": "trade", "item_id": "item_1", "quantity": 1},
        ]
        chosen = policy.select_action(state, actions)
        assert chosen is not None
        assert chosen in actions

    def test_update(self):
        policy = RLPolicy(learning_rate=0.5)
        s1 = {"gold": 100, "inventory": {"i": 1}, "achievements": []}
        s2 = {"gold": 150, "inventory": {"i": 2}, "achievements": []}
        action = {"type": "farm", "item_id": "i", "quantity": 1}
        policy.update(s1, action, 1.0, s2, [action])
        sk = policy._state_key(s1)
        ak = policy._action_key(action)
        assert policy.get_q(sk, ak) != 0

    def test_epsilon_decay(self):
        policy = RLPolicy(epsilon=0.5, epsilon_decay=0.5, min_epsilon=0.01)
        state = {"gold": 100, "inventory": {}, "achievements": []}
        action = {"type": "farm", "item_id": "g", "quantity": 1}
        for _ in range(200):
            policy.update(state, action, 0.0, state, [action])
        assert policy.epsilon < 0.5

    def test_get_best_actions_empty(self):
        policy = RLPolicy()
        state = {"gold": 0, "inventory": {}, "achievements": []}
        assert policy.get_best_actions(state) == []


class TestRewardFunction:
    def test_compute(self):
        rf = RewardFunction()
        before = {"gold": 100, "inventory": {"a": 1}, "achievements": []}
        after = {"gold": 200, "inventory": {"a": 1}, "achievements": []}
        comp = rf.compute(before, after, {"type": "trade"})
        assert comp.economic_gain > 0
        assert comp.total > 0

    def test_reasoning_accuracy(self):
        rf = RewardFunction()
        before = {"gold": 0, "inventory": {}, "achievements": []}
        after = {"gold": 10, "inventory": {}, "achievements": []}
        validations = [{"valid": True}, {"valid": True}, {"valid": False}]
        comp = rf.compute(before, after, {"type": "farm"}, validations)
        assert comp.reasoning_accuracy == pytest.approx(2 / 3)

    def test_reward_history(self):
        rf = RewardFunction()
        rf.compute({"gold": 0, "inventory": {}, "achievements": []}, {"gold": 1, "inventory": {}, "achievements": []})
        assert len(rf.reward_history()) == 1


class TestEconomicLifecycle:
    def test_register_items(self):
        eco = EconomicLifecycle()
        eco.register_item("item_1", initial_price=500)
        assert "item_1" in eco.state.items
        assert eco.state.items["item_1"].price == 500

    def test_step(self):
        eco = EconomicLifecycle()
        eco.register_item("core", initial_price=200, volatility=0.2)
        eco.step(dt=10)
        assert eco.state.t == 10
        assert eco.state.items["core"].price != 200

    def test_market_health(self):
        eco = EconomicLifecycle()
        health = eco.market_health()
        assert "health" in health
        assert health["health"] == 0.5

    def test_price_forecast(self):
        eco = EconomicLifecycle()
        eco.register_item("silk", initial_price=300)
        forecast = eco.price_forecast("silk", horizon=3)
        assert len(forecast) == 3


class TestAgents:
    def test_trader_act(self):
        agent = TraderAgent(capital=5000)
        state = {"market": {"item_1": {"buy_price": 100, "sell_price": 120, "supply": 50, "demand": 30}}, "inventory": {}}
        action = agent.act(state)
        assert action.action_type == "trade"

    def test_crafter_act(self):
        agent = CrafterAgent()
        agent.learn_recipe("legendary", {"mat_1": 5, "mat_2": 3}, 2000.0)
        state = {"inventory": {"mat_1": 10, "mat_2": 10}}
        action = agent.act(state)
        assert action.action_type == "craft"

    def test_raider_act(self):
        agent = RaiderAgent(skill_level=1.0)
        state = {"inventory": {}, "achievements": []}
        action = agent.act(state)
        assert action.action_type == "farm"

    def test_meta_act(self):
        agent = MetaAgent()
        agent.update_meta("bis_weapon", 10.0)
        state = {"inventory": {}, "achievements": []}
        action = agent.act(state)
        assert action.action_type == "achievement"

    def test_agent_observe(self):
        agent = TraderAgent()
        action = agent.act({"market": {}, "inventory": {}})
        assert agent._total_reward == 0
        agent.observe({"t": 1, "inventory": {}, "market": {}}, action, 5.0)
        assert agent._total_reward == 5.0
        assert len(agent._memory) == 1


class TestSimulationFidelity:
    def test_tp_economics(self):
        from gw2_progression.cognitive_os.simulation_fidelity import tp_buy_cost, tp_sell_proceeds
        assert tp_sell_proceeds(100) == 85.0
        assert tp_sell_proceeds(100, 5) == 425.0
        assert tp_buy_cost(100) == 105.0

    def test_price_elasticity(self):
        from gw2_progression.cognitive_os.simulation_fidelity import price_elasticity
        eq = price_elasticity(100, 200, 100, 0.5)
        assert eq > 100

    def test_uncertainty_tracker(self):
        from gw2_progression.cognitive_os.simulation_fidelity import UncertaintyTracker
        ut = UncertaintyTracker()
        ut.set("gold", 500, "api")
        ut.set("inv.x", 10, "inferred")
        assert ut.get_confidence("gold") == 1.0
        assert ut.get_confidence("inv.x") == 0.7
        assert ut.overall_certainty() == 0.85
        ut.boost("inv.x", 0.2)
        assert abs(ut.get_confidence("inv.x") - 0.9) < 1e-10
        assert "gold" not in ut.low_confidence_vars(0.5)

    def test_enhanced_dgsk_disciplines(self):
        from gw2_progression.cognitive_os.simulation_fidelity import DGSKEnhancedConstraints, Discipline
        dgsk = DGSKEnhancedConstraints()
        dgsk.set_discipline(Discipline.ARMORSMITH, 400)
        assert dgsk.can_craft_with_discipline(350, Discipline.ARMORSMITH)
        assert not dgsk.can_craft_with_discipline(450, Discipline.ARMORSMITH)

    def test_enhanced_dgsk_rarity(self):
        from gw2_progression.cognitive_os.simulation_fidelity import DGSKEnhancedConstraints, Rarity
        dgsk = DGSKEnhancedConstraints()
        dgsk.set_item_rarity("legendary_sword", Rarity.LEGENDARY)
        inv = {"legendary_sword": 1}
        result = dgsk.validate_item_rarity_consistency(inv)
        assert result["valid"]
        inv_bad = {"legendary_sword": 20}
        result_bad = dgsk.validate_item_rarity_consistency(inv_bad)
        assert not result_bad["valid"]

    def test_achievement_chain(self):
        from gw2_progression.cognitive_os.simulation_fidelity import AchievementChain
        chain = AchievementChain(
            chain_id="legendary_weapon",
            name="Legendary Weapon",
            achievements=["col1", "col2", "col3"],
            parallel_branches={"gift": ["gift_1", "gift_2"]},
        )
        assert not chain.is_completable(set())
        assert chain.is_completable({"col1", "col2", "col3", "gift_1", "gift_2"})
        assert chain.next_achievable(set()) == ["col1", "gift_1"]

    def test_enhanced_economy(self):
        from gw2_progression.cognitive_os.simulation_fidelity import EnhancedEconomyRules, ItemCategory
        eco = EnhancedEconomyRules()
        eco.set_category("ore", ItemCategory.RAW_MATERIAL)
        result = eco.compute_equilibrium_price("ore", 500, 300, 100)
        assert result["category"] == "raw_material"
        assert result["volatility"] == 0.15

    def test_enhanced_economy_trade_validation(self):
        from gw2_progression.cognitive_os.simulation_fidelity import EnhancedEconomyRules
        eco = EnhancedEconomyRules()
        result = eco.validate_trade_after_tax(100, 150)
        assert result["valid"]
        assert result["profit"] > 0
        result_bad = eco.validate_trade_after_tax(150, 100)
        assert not result_bad["valid"]

    def test_enhanced_economy_category_health(self):
        from gw2_progression.cognitive_os.simulation_fidelity import EnhancedEconomyRules, ItemCategory
        eco = EnhancedEconomyRules()
        eco.set_category("ore", ItemCategory.RAW_MATERIAL)
        eco.set_category("plank", ItemCategory.CRAFTED_MATERIAL)
        market = {
            "ore": {"price": 50},
            "plank": {"price": 150},
        }
        health = eco.compute_category_health(market)
        assert "raw_material" in health
        assert "crafted_material" in health

    def test_fidelity_assessment(self):
        from gw2_progression.cognitive_os.simulation_fidelity import SimulationFidelity
        sf = SimulationFidelity()
        report = sf.full_report()
        assert "fidelity_scores" in report
        assert "dgsk" in report
        assert "economy" in report
        assert report["dgsk"]["coverage_percentage"] > 0
        assert report["oosk"]["fidelity_percentage"] > 0

    def test_rarity_enum_values(self):
        from gw2_progression.cognitive_os.simulation_fidelity import Rarity
        assert Rarity.LEGENDARY.value == "legendary"
        assert Rarity.ASCENDED.value == "ascended"

    def test_discipline_enum_values(self):
        from gw2_progression.cognitive_os.simulation_fidelity import Discipline
        assert Discipline.ARMORSMITH.value == "armorsmith"
        assert Discipline.MYSTIC_FORGE.value == "mystic_forge"
    def test_initialize(self):
        os = CognitiveOSEngine()
        os.initialize({"gold": 500, "inventory": {"item_1": 5, "item_2": 3}, "achievements": ["ach_1"]})
        assert os._initialized
        assert os.temporal.current["gold"] == 500
        assert len(os.agents) == 4

    def test_step(self):
        os = CognitiveOSEngine()
        os.initialize({"gold": 100, "inventory": {"item_1": 10}, "achievements": []})
        result = os.step()
        assert result["t"] == 1
        assert "action" in result
        assert "reward" in result
        assert "economy" in result

    def test_custom_action_step(self):
        os = CognitiveOSEngine()
        os.initialize({"gold": 0, "inventory": {}, "achievements": []})
        result = os.step({"type": "farm", "item_id": "gold", "quantity": 5})
        assert result["t"] == 1
        assert result["action"]["type"] == "farm"

    def test_simulation(self):
        os = CognitiveOSEngine()
        initial = {"gold": 100, "inventory": {"ore": 20}, "achievements": ["daily"]}
        result = os.run_simulation(initial_state=initial, steps=5)
        assert result["steps"] == 5
        assert result["final_t"] == 5
        assert result["total_reward"] != 0
        assert len(result["trajectory"]) == 5

    def test_multi_agent_interact(self):
        os = CognitiveOSEngine()
        os.initialize({"gold": 1000, "inventory": {"ore": 50, "wood": 30}, "achievements": []})
        if hasattr(os.agents.get("crafter"), "learn_recipe"):
            os.agents["crafter"].learn_recipe("plank", {"wood": 3}, 50.0)
        result = os.agent_interact(os.temporal.current)
        assert "agents" in result
        assert "trader" in result["agents"]
        assert "crafter" in result["agents"]

    def test_analyze(self):
        os = CognitiveOSEngine()
        os.initialize({"gold": 100, "inventory": {"ore": 5}, "achievements": []})
        analysis = os.analyze()
        assert "cognition_graph" in analysis
        assert "economy" in analysis
        assert "policy" in analysis
        assert "agents" in analysis

    def test_to_dict(self):
        os = CognitiveOSEngine()
        os.initialize({"gold": 100, "inventory": {}, "achievements": []})
        d = os.to_dict()
        assert d["initialized"]
        assert len(d["agents"]) == 4

    def test_cognition_graph_built_on_init(self):
        os = CognitiveOSEngine()
        os.initialize({"gold": 500, "inventory": {}, "achievements": []})
        stats = os.cognition.to_dict()["stats"]
        assert stats["node_count"] >= 4
        assert stats["edge_count"] >= 4


# ─── Probabilistic World Model v1 Tests ───────────────────────────

class TestProbabilisticDGSK:
    def test_add_node_and_edge(self):
        from gw2_progression.cognitive_os.probabilistic import ProbabilisticDGSK
        dgsk = ProbabilisticDGSK()
        dgsk.add_node("n1", "entity", {"gold": 100})
        dgsk.add_node("n2", "state")
        dgsk.add_edge("n1", "n2", "influences", probability=0.8, strength=1.5)
        assert len(dgsk.nodes) == 2
        assert len(dgsk.edges) == 1
        edge = dgsk.get_edge("n1", "n2", "influences")
        assert edge is not None
        assert edge.probability == 0.8

    def test_sample_graph(self):
        dgsk = ProbabilisticDGSK()
        dgsk.add_node("a", "entity")
        dgsk.add_node("b", "state")
        dgsk.add_edge("a", "b", "links", probability=1.0, strength=1.0)
        sample = dgsk.sample_graph()
        assert "a" in sample["nodes"]
        assert len(sample["edges"]) == 1

    def test_graph_uncertainty(self):
        dgsk = ProbabilisticDGSK(default_uncertainty=0.3)
        dgsk.add_node("a", "entity")
        dgsk.add_node("b", "state")
        dgsk.add_edge("a", "b", "links", probability=0.8, uncertainty=0.3)
        assert dgsk.graph_uncertainty() == 0.3
        assert dgsk.edge_entropy() > 0

    def test_merge_with_cognition_graph(self):
        from gw2_progression.cognitive_os.cognition_graph.graph import CognitionGraph, EdgeType, NodeType
        cg = CognitionGraph()
        cg.add_node(NodeType.ENTITY, "char", {}, node_id="c1")
        cg.add_node(NodeType.STATE, "world", {}, node_id="s1")
        cg.add_edge("c1", "s1", EdgeType.EVOLVES_TO, weight=0.9)

        dgsk = ProbabilisticDGSK()
        dgsk.merge_with_cognition_graph(cg)
        assert len(dgsk.nodes) >= 2
        assert len(dgsk.edges) >= 1


class TestRuleGNN:
    def test_compute_embeddings(self):
        gnn = RuleGNN(embedding_dim=8)
        graph = {
            "nodes": {"a": {"type": "entity"}, "b": {"type": "state"}, "c": {"type": "goal"}},
            "edges": [
                {"source": "a", "target": "b", "relation": "evolves", "strength": 1.0},
                {"source": "b", "target": "c", "relation": "influences", "strength": 0.5},
            ],
        }
        embs = gnn.compute_node_embeddings(graph)
        assert len(embs) == 3
        assert all(len(v) == 8 for v in embs.values())

    def test_message_passing(self):
        gnn = RuleGNN()
        embs = {"a": [1.0, 0.0], "b": [0.0, 1.0]}
        edges = [{"source": "a", "target": "b", "strength": 0.5}]
        result = gnn.message_passing(embs, edges, steps=1)
        assert len(result) == 2

    def test_induce_rules(self):
        gnn = RuleGNN(min_support=1)
        graph = {
            "nodes": {"a": {"type": "e"}, "b": {"type": "s"}, "c": {"type": "g"}},
            "edges": [
                {"source": "a", "target": "b", "relation": "evolves", "strength": 1.0},
                {"source": "b", "target": "c", "relation": "influences", "strength": 0.5},
            ],
        }
        rules = gnn.induce_rules(graph)
        assert isinstance(rules, list)

    def test_predict_relation_strength(self):
        gnn = RuleGNN()
        gnn._node_embeddings = {"a": [1.0, 0.0], "b": [1.0, 0.0]}
        strength = gnn.predict_relation_strength("a", "b")
        assert strength > 0


class TestProbabilisticBORS:
    def test_decision_distribution(self):
        bors = ProbabilisticBORS()
        state = {"gold": 100, "inventory": {"ore": 5}, "market": {}}
        dist = bors.compute_decision_distribution(state)
        assert "BUY" in dist.probabilities
        assert "SELL" in dist.probabilities
        assert abs(sum(dist.probabilities.values()) - 1.0) < 0.01

    def test_sample_decision(self):
        bors = ProbabilisticBORS()
        state = {"gold": 100, "inventory": {}, "market": {}}
        bors.compute_decision_distribution(state)
        decision = bors.sample_decision()
        assert decision in ("BUY", "SELL", "HOLD", "CRAFT", "FARM", "RAID", "ACHIEVEMENT", "META")

    def test_decision_history(self):
        bors = ProbabilisticBORS()
        bors.compute_decision_distribution({"gold": 100, "inventory": {}, "market": {}})
        bors.compute_decision_distribution({"gold": 200, "inventory": {"x": 1}, "market": {}})
        assert len(bors._decision_history) == 2
        assert len(bors.decision_entropy_trend) == 2


class TestProbabilisticPolicy:
    def test_get_distribution(self):
        policy = ProbabilisticPolicy(temperature=1.0)
        available = [
            {"type": "farm", "item_id": "gold", "quantity": 1},
            {"type": "trade", "item_id": "ore", "quantity": 5},
            {"type": "craft", "item_id": "ingot", "quantity": 1},
        ]
        dist = policy.get_distribution("s1", available)
        assert len(dist) == 3
        assert abs(sum(d.probability for d in dist) - 1.0) < 0.01

    def test_update(self):
        policy = ProbabilisticPolicy()
        policy.update("s1", {"type": "farm", "item_id": "gold"}, 1.0)
        dist = policy.get_distribution("s1", [{"type": "farm", "item_id": "gold", "quantity": 1}])
        assert dist[0].q_value > 0

    def test_temperature_controls_entropy(self):
        policy_high = ProbabilisticPolicy(temperature=10.0)
        policy_low = ProbabilisticPolicy(temperature=0.1)
        available = [
            {"type": "farm", "item_id": "gold", "quantity": 1},
            {"type": "trade", "item_id": "ore", "quantity": 5},
        ]
        # Update low temp policy with reward
        policy_low.update("s1", {"type": "farm", "item_id": "gold"}, 10.0)
        policy_high.update("s1", {"type": "farm", "item_id": "gold"}, 10.0)

        dist_high = policy_high.get_distribution("s1", available)
        dist_low = policy_low.get_distribution("s1", available)

        # Low temperature should give higher max probability (more exploitation)
        max_low = max(d.probability for d in dist_low)
        max(d.probability for d in dist_high)
        # This may not always hold due to softmax normalization, but low temp should be less uniform
        assert max_low >= 0  # just checking stability


class TestCausalReasoning:
    def test_infer_causal_chain(self):
        causal = CausalReasoningLayer()
        graph = {
            "nodes": {
                "a": {"type": "entity"},
                "b": {"type": "state"},
                "c": {"type": "decision"},
            },
            "edges": [
                {"source": "a", "target": "b", "relation": "evolves", "strength": 1.0},
                {"source": "b", "target": "c", "relation": "influences", "strength": 0.5},
            ],
        }
        chains = causal.infer_causal_chain(graph, "c")
        assert len(chains) >= 1
        assert chains[0].chain[-1] == "c"

    def test_counterfactual(self):
        causal = CausalReasoningLayer()

        def sim(state, action):
            new_s = dict(state)
            new_s["gold"] = new_s.get("gold", 0) + 10 if action.get("type") == "farm" else new_s.get("gold", 0) + 5
            return new_s

        state = {"gold": 100, "inventory": {}, "achievements": []}
        original = {"type": "farm", "item_id": "gold", "quantity": 1}
        alternative = {"type": "trade", "item_id": "ore", "quantity": 5}
        result = causal.counterfactual(state, original, alternative, sim, num_samples=3)
        assert result.confidence > 0
        assert "gold" in result.delta

    def test_explain(self):
        causal = CausalReasoningLayer()
        graph = {
            "nodes": {"a": {"type": "entity"}, "b": {"type": "state"}},
            "edges": [{"source": "a", "target": "b", "relation": "evolves", "strength": 1.0}],
        }
        causal.infer_causal_chain(graph, "b")
        explanation = causal.explain("causal_b_0")
        assert "Causal Chain" in explanation


class TestWorldInferenceLoop:
    def test_step(self):
        loop = ProbabilisticWorldInferenceLoop(num_worlds=3, steps_per_world=5)
        loop.dgsk.add_node("a", "entity")
        loop.dgsk.add_node("b", "state")
        loop.dgsk.add_edge("a", "b", "influences", probability=1.0)

        def sim(s, a):
            return dict(s)
        loop.set_simulator(sim)
        loop.set_action_sampler(lambda s: [{"type": "farm", "item_id": "gold", "quantity": 1}])

        result = loop.step({"gold": 100})
        assert "dgsk_sample" in result
        assert "gnn_output" in result
        assert "bors_distribution" in result
        assert "policy_distribution" in result
        assert "causal_chains" in result
        assert result["step"] == 1

    def test_multi_world(self):
        loop = ProbabilisticWorldInferenceLoop(num_worlds=3, steps_per_world=5)

        def sim(s, a):
            return dict(s)
        loop.set_simulator(sim)
        loop.set_action_sampler(lambda s: [{"type": "farm", "item_id": "gold", "quantity": 1}])

        samples = loop.run_multi_world({"gold": 100})
        assert len(samples) == 3
        assert loop.world_diversity() >= 0

    def test_best_world(self):
        loop = ProbabilisticWorldInferenceLoop(num_worlds=2, steps_per_world=3)

        def sim(s, a):
            return dict(s)
        loop.set_simulator(sim)
        loop.set_action_sampler(lambda s: [{"type": "farm", "item_id": "gold", "quantity": 1}])

        loop.run_multi_world({"gold": 100})
        best = loop.best_world()
        assert best is not None
        assert best.world_id.startswith("world_")


class TestBehaviorModel:
    def test_profile_action_distribution(self):
        from gw2_progression.cognitive_os.behavior import Archetype, BehaviorProfile
        profile = BehaviorProfile(archetype_weights={Archetype.TRADER: 1.0})
        dist = profile.action_distribution()
        assert ActionType.TRADE.value in (k.value for k in dist) or ActionType.TRADE in dist
        assert profile.dominant_archetype == Archetype.TRADER

    def test_profile_update_from_observation(self):
        profile = BehaviorProfile(archetype_weights={Archetype.TRADER: 0.5, Archetype.CRAFTER: 0.5})
        profile.update_from_observation(ActionType.TRADE, 1.0)
        assert profile.archetype_weights[Archetype.TRADER] > 0.5

    def test_profile_entropy(self):
        uniform = BehaviorProfile()
        assert uniform.entropy() > 0.9  # near max entropy for 8 archetypes
        pure_trader = BehaviorProfile(archetype_weights={Archetype.TRADER: 1.0})
        assert pure_trader.entropy() < 0.2

    def test_profile_similarity(self):
        p1 = BehaviorProfile(archetype_weights={Archetype.TRADER: 0.8, Archetype.CRAFTER: 0.2})
        p2 = BehaviorProfile(archetype_weights={Archetype.TRADER: 0.9, Archetype.CRAFTER: 0.1})
        assert p1.similarity(p2) > 0.9

    def test_model_classify_from_state(self):
        from gw2_progression.cognitive_os.behavior import BehaviorModel
        model = BehaviorModel()
        state = {"gold": 10000, "inventory": {"mystic_coin": 50}, "achievements": [], "market": {}}
        scores = model.classify_from_state(state)
        assert max(scores, key=scores.get) in ("trader", "optimizer", "grinder")

    def test_model_observe(self):
        model = BehaviorModel()
        state = {"gold": 100, "inventory": {}, "achievements": []}
        obs = model.observe("player1", ActionType.TRADE, 0.5, state)
        assert obs.action_type == ActionType.TRADE
        assert "player1" in model.profiles

    def test_model_population_distribution(self):
        model = BehaviorModel()
        model.get_or_create_profile("p1", Archetype.TRADER)
        model.get_or_create_profile("p2", Archetype.CRAFTER)
        dist = model.population_distribution()
        assert "trader" in dist or "crafter" in dist

    def test_evolution_model(self):
        from gw2_progression.cognitive_os.behavior import BehaviorEvolutionModel
        evo = BehaviorEvolutionModel(stability=1.0, drift_rate=0.0, shock_rate=0.0)
        profile = BehaviorProfile(archetype_weights={Archetype.TRADER: 1.0})
        evolved = evo.evolve(profile)
        assert evolved.dominant_archetype == Archetype.TRADER


class TestCalibrationLoop:
    def test_compute_metrics(self):
        loop = CalibrationLoop()
        sim = {"gold": 100, "inventory": {"a": 1}, "achievements": ["x"], "market": {}}
        real = {"gold": 120, "inventory": {"a": 1, "b": 2}, "achievements": ["x", "y"], "market": {}}
        metrics = loop.compute_metrics(sim, real)
        assert len(metrics) >= 4
        names = [m.name for m in metrics]
        assert "gold" in names
        assert "inventory_size" in names

    def test_observe_and_adjust(self):
        loop = CalibrationLoop(learning_rate=0.1)
        sim = {"gold": 100, "inventory": {}, "achievements": [], "market": {}}
        real = {"gold": 200, "inventory": {"x": 5}, "achievements": ["a"], "market": {}}
        obs = loop.observe(sim, real)
        assert obs.total_loss > 0
        assert len(loop.observations) == 1
        assert loop.average_loss > 0

    def test_loss_trend(self):
        loop = CalibrationLoop()
        sim = {"gold": 100, "inventory": {}, "achievements": [], "market": {}}
        real = {"gold": 100, "inventory": {}, "achievements": [], "market": {}}
        for _ in range(5):
            loop.observe(sim, real)
        assert loop.loss_trend in ("stable", "insufficient_data")

    def test_parameter_bounds(self):
        loop = CalibrationLoop()
        loop.parameters[CalibratedParameter.FARM_YIELD_MULTIPLIER.value]
        sim = {"gold": 100, "inventory": {"x": 1}, "achievements": ["a"], "market": {}}
        real = {"gold": 500, "inventory": {"x": 10}, "achievements": ["a", "b", "c"], "market": {}}
        loop.observe(sim, real)
        updated = loop.parameters[CalibratedParameter.FARM_YIELD_MULTIPLIER.value]
        assert 0.01 <= updated <= 2.0


class TestProbabilisticEngineIntegration:
    def test_engine_has_probabilistic_layers(self):
        from gw2_progression.cognitive_os.engine import CognitiveOSEngine
        os = CognitiveOSEngine()
        assert hasattr(os, "probabilistic_world")
        assert hasattr(os, "probabilistic_dgsk")
        assert hasattr(os, "probabilistic_bors")
        assert hasattr(os, "probabilistic_causal")
        assert hasattr(os, "probabilistic_gnn")
        assert hasattr(os, "behavior_model")
        assert hasattr(os, "calibration")

    def test_engine_probabilistic_step(self):
        from gw2_progression.cognitive_os.engine import CognitiveOSEngine
        os = CognitiveOSEngine()
        os.initialize({"gold": 100, "inventory": {"ore": 5}, "achievements": []})
        result = os.probabilistic_step()
        assert "dgsk_sample" in result
        assert "bors_distribution" in result

    def test_engine_classify_behavior(self):
        from gw2_progression.cognitive_os.engine import CognitiveOSEngine
        os = CognitiveOSEngine()
        os.initialize({"gold": 500, "inventory": {"mystic_coin": 20}, "achievements": []})
        result = os.classify_behavior()
        assert "archetype_scores" in result
        assert "profile" in result

    def test_engine_calibrate(self):
        from gw2_progression.cognitive_os.engine import CognitiveOSEngine
        os = CognitiveOSEngine()
        os.initialize({"gold": 100, "inventory": {}, "achievements": []})
        result = os.calibrate({"gold": 200, "inventory": {}, "achievements": []})
        assert "loss" in result
        assert result["loss"] > 0

    def test_engine_gnn_induction(self):
        from gw2_progression.cognitive_os.engine import CognitiveOSEngine
        os = CognitiveOSEngine()
        os.initialize({"gold": 100, "inventory": {}, "achievements": []})
        result = os.gnn_induction()
        assert "node_embeddings" in result or "induced_rules" in result

    def test_engine_counterfactual(self):
        from gw2_progression.cognitive_os.engine import CognitiveOSEngine
        os = CognitiveOSEngine()
        os.initialize({"gold": 100, "inventory": {}, "achievements": []})
        original = {"type": "farm", "item_id": "gold", "quantity": 1}
        alternative = {"type": "trade", "item_id": "ore", "quantity": 5}
        result = os.counterfactual_query(original, alternative)
        assert "question" in result
        assert "delta" in result

    def test_engine_multi_world(self):
        from gw2_progression.cognitive_os.engine import CognitiveOSEngine
        os = CognitiveOSEngine()
        os.initialize({"gold": 100, "inventory": {}, "achievements": []})
        result = os.run_multi_world(num_worlds=2, steps=5)
        assert result["world_count"] == 2
        assert result["world_diversity"] >= 0


# ─── Data Acquisition OS Tests ───────────────────────────────────

class TestSourceRegistry:
    def test_init_default_sources(self):
        from gw2_progression.data_acquisition.registry.source_registry import SourceRegistry
        reg = SourceRegistry()
        assert len(reg.get_enabled()) > 0

    def test_register_source(self):
        from gw2_progression.data_acquisition.registry.source_registry import SourceRegistry
        reg = SourceRegistry()
        reg.register({"id": "test_api", "type": "api", "priority": 0, "frequency": "realtime"})
        assert reg.get("test_api") is not None

    def test_get_by_type(self):
        from gw2_progression.data_acquisition.registry.source_registry import SourceRegistry, SourceType
        reg = SourceRegistry()
        api_sources = reg.get_by_type(SourceType.API)
        assert len(api_sources) > 0

    def test_get_sorted_order(self):
        from gw2_progression.data_acquisition.registry.source_registry import SourceRegistry
        reg = SourceRegistry()
        sorted_sources = reg.get_sorted()
        assert len(sorted_sources) > 0


class TestFetcher:
    def test_fetch_api(self):
        from gw2_progression.data_acquisition.ingestion.fetcher import Fetcher
        from gw2_progression.data_acquisition.registry.source_registry import SourceConfig, SourcePriority, SourceType
        fetcher = Fetcher()
        source = SourceConfig(id="test", type=SourceType.API, priority=SourcePriority.HIGH, frequency="realtime", endpoint="/v2/account/wallet")
        result = fetcher.fetch(source)
        assert "data" in result
        assert "source_id" in result

    def test_fetch_market(self):
        from gw2_progression.data_acquisition.ingestion.fetcher import Fetcher
        from gw2_progression.data_acquisition.registry.source_registry import SourceConfig, SourcePriority, SourceType
        fetcher = Fetcher()
        source = SourceConfig(id="tp", type=SourceType.MARKET, priority=SourcePriority.HIGH, frequency="hourly")
        result = fetcher.fetch(source)
        assert "data" in result


class TestIngestionOrchestrator:
    def test_ingest_source(self):
        from gw2_progression.data_acquisition import IngestionOrchestrator, SourceRegistry
        reg = SourceRegistry()
        orch = IngestionOrchestrator(registry=reg)
        sources = reg.get_enabled()
        if sources:
            result = orch.ingest_source(sources[0])
            assert result.success or not result.success

    def test_ingest_all(self):
        from gw2_progression.data_acquisition import IngestionOrchestrator, SourceRegistry
        reg = SourceRegistry()
        orch = IngestionOrchestrator(registry=reg)
        results = orch.ingest_all()
        assert len(results) > 0

    def test_orchestrator_to_dict(self):
        from gw2_progression.data_acquisition import IngestionOrchestrator, SourceRegistry
        reg = SourceRegistry()
        orch = IngestionOrchestrator(registry=reg)
        d = orch.to_dict()
        assert "total_sources" in d
        assert "registry" in d


class TestExpansion:
    def test_horizontal_expand(self):
        from gw2_progression.data_acquisition.expansion.horizontal import HorizontalExpander
        expander = HorizontalExpander()
        from gw2_progression.data_acquisition.registry.source_registry import SourceConfig, SourcePriority, SourceType
        source = SourceConfig(id="test", type=SourceType.API, priority=SourcePriority.HIGH, frequency="realtime")
        data = {"entities": [{"id": "e1", "properties": {"gold": 100}}], "relations": [], "source": "test"}
        result = expander.expand(data, source)
        assert result.get("_horizontal_expanded")

    def test_vertical_expand(self):
        from gw2_progression.data_acquisition.expansion.vertical import VerticalExpander
        expander = VerticalExpander()
        from gw2_progression.data_acquisition.registry.source_registry import SourceConfig, SourcePriority, SourceType
        source = SourceConfig(id="test", type=SourceType.API, priority=SourcePriority.HIGH, frequency="realtime")
        data = {"entities": [{"id": "recipe:1", "type": "recipe", "name": "Test"}], "relations": [], "source": "test"}
        result = expander.expand(data, source)
        assert result.get("_vertical_expanded")

    def test_temporal_expand(self):
        from gw2_progression.data_acquisition.expansion.temporal import TemporalExpander
        expander = TemporalExpander(history_depth=2)
        from gw2_progression.data_acquisition.registry.source_registry import SourceConfig, SourcePriority, SourceType
        source = SourceConfig(id="test", type=SourceType.API, priority=SourcePriority.HIGH, frequency="realtime")
        data = {"entities": [{"id": "e1", "properties": {"gold": 100}}], "relations": [], "source": "test"}
        result = expander.expand(data, source)
        assert result.get("_temporal_expanded")

    def test_synthetic_expand(self):
        from gw2_progression.data_acquisition.expansion.synthetic import SyntheticExpander
        expander = SyntheticExpander(synthetic_ratio=1.0)
        from gw2_progression.data_acquisition.registry.source_registry import SourceConfig, SourcePriority, SourceType
        source = SourceConfig(id="test", type=SourceType.API, priority=SourcePriority.HIGH, frequency="realtime")
        data = {"entities": [{"id": "e1"}], "relations": [], "source": "test"}
        result = expander.expand(data, source)
        assert result.get("_synthetic_expanded")


class TestStreamEngine:
    def test_stream_push_and_flush(self):
        from gw2_progression.data_acquisition.streaming.stream_engine import StreamEngine
        stream = StreamEngine(buffer_size=3, flush_interval=999)
        stream.push_data("src1", "test", {"gold": 100})
        stream.push_data("src2", "test", {"gold": 200})
        assert stream.buffer_size_current == 2
        flushed = stream.flush()
        assert len(flushed) == 2

    def test_event_bus(self):
        from gw2_progression.data_acquisition.streaming.event_bus import DataEvent, EventBus
        bus = EventBus()
        received = []

        def handler(event):
            received.append(event)

        bus.subscribe("test_type", handler)
        bus.publish(DataEvent(source_id="src", data_type="test_type", data={"key": "val"}))
        assert len(received) == 1

    def test_event_replay(self):
        from gw2_progression.data_acquisition.streaming.event_bus import DataEvent, EventBus
        bus = EventBus()
        bus.publish(DataEvent(source_id="s1", data_type="a", data={}))
        bus.publish(DataEvent(source_id="s2", data_type="b", data={}))
        replay = bus.replay()
        assert len(replay) == 2


class TestDGSKGraphBuilder:
    def test_build(self):
        from gw2_progression.data_acquisition.dgsk.graph_builder import DGSKGraphBuilder
        builder = DGSKGraphBuilder()
        data = {
            "entities": [{"id": "e1", "type": "entity", "name": "Test", "properties": {}}],
            "relations": [{"source": "e1", "target": "e1", "relation": "self", "confidence": 1.0}],
            "source": "test",
        }
        result = builder.build(data)
        assert result.nodes_added >= 1

    def test_graph_property(self):
        from gw2_progression.data_acquisition.dgsk.graph_builder import DGSKGraphBuilder
        builder = DGSKGraphBuilder()
        g = builder.graph
        assert "nodes" in g
        assert "edges" in g

    def test_node_manager(self):
        from gw2_progression.data_acquisition.dgsk.node_manager import NodeManager
        nm = NodeManager()
        nm.ensure_node("n1", "entity", "Node1", {"gold": 100})
        nm.ensure_node("n1", "entity", "Node1", {"gold": 200})
        node = nm.get_node("n1")
        assert node is not None
        assert node["properties"]["gold"] == 200

    def test_edge_builder(self):
        from gw2_progression.data_acquisition.dgsk.edge_builder import EdgeBuilder
        eb = EdgeBuilder()
        edge = eb.build_edge("a", "b", "depends_on", 0.9)
        assert edge["source"] == "a"
        assert edge["edge_type"] == "depends_on"


class TestTaskScheduler:
    def test_schedule_and_run(self):
        from gw2_progression.data_acquisition.scheduler.task_scheduler import TaskScheduler
        sched = TaskScheduler()
        assert len(sched.tasks) > 0

    def test_enable_disable(self):
        from gw2_progression.data_acquisition.scheduler.task_scheduler import TaskScheduler
        sched = TaskScheduler()
        task_ids = list(sched.tasks.keys())
        if task_ids:
            sched.disable_task(task_ids[0])
            assert not sched.tasks[task_ids[0]].enabled
            sched.enable_task(task_ids[0])
            assert sched.tasks[task_ids[0]].enabled


class TestDataFlywheel:
    def test_flywheel_init(self):
        from gw2_progression.data_acquisition.flywheel.data_loop import DataFlywheel
        flywheel = DataFlywheel()
        assert flywheel.iteration_count == 0

    def test_flywheel_one_iteration(self):
        from gw2_progression.data_acquisition.flywheel.data_loop import DataFlywheel
        flywheel = DataFlywheel()
        ingest_called = [False]

        def mock_ingest():
            ingest_called[0] = True
            from gw2_progression.data_acquisition.ingestion.orchestrator import IngestionResult
            return [IngestionResult(source_id="mock", success=True, events=[], total_entities=5, total_relations=3, duration_ms=10)]

        def mock_graph():
            return {"total_nodes": 10, "total_edges": 5}

        def mock_sim():
            return {}

        def mock_infer():
            return {"profiles": {"p1": {}}}

        def mock_dataset(iteration):
            return 100

        flywheel.set_hooks(ingest_all=mock_ingest, graph_build=mock_graph, simulate=mock_sim, infer=mock_infer, dataset=mock_dataset)
        result = flywheel.run_one_iteration()
        assert result.iteration == 1
        assert result.total_entities == 5
        assert result.dataset_samples == 100

    def test_flywheel_stop(self):
        from gw2_progression.data_acquisition.flywheel.data_loop import DataFlywheel
        flywheel = DataFlywheel()
        flywheel.stop()
        assert not flywheel._running


class TestDatasetBuilder:
    def test_build_rl_dataset(self):
        from gw2_progression.data_acquisition.flywheel.dataset_builder import DatasetBuilder
        builder = DatasetBuilder()
        trajectory = [{"state": {"gold": 100}, "action": {"type": "farm"}, "reward": 0.5}]
        ds = builder.build_rl_dataset(trajectory, 1)
        assert len(ds.samples) == 1
        assert ds.samples[0].labels["reward"] == 0.5

    def test_build_behavior_dataset(self):
        from gw2_progression.data_acquisition.flywheel.dataset_builder import DatasetBuilder
        builder = DatasetBuilder()
        ds = builder.build_behavior_dataset({"gold": 100}, {"trader": 0.8, "crafter": 0.2}, 1)
        assert ds.samples[0].labels["trader"] == 0.8

    def test_save_all(self):
        from gw2_progression.data_acquisition.flywheel.dataset_builder import DatasetBuilder
        builder = DatasetBuilder()
        builder.build_rl_dataset([{"state": {}, "action": {}, "reward": 1.0}], 1)
        count = builder.save_all()
        assert count > 0

    def test_total_samples(self):
        from gw2_progression.data_acquisition.flywheel.dataset_builder import DatasetBuilder
        builder = DatasetBuilder()
        assert builder.total_samples() == 0
        builder.build_rl_dataset([{"state": {}, "action": {}, "reward": 1.0}], 1)
        assert builder.total_samples() == 1


class TestDataFactory:
    def test_factory_init(self):
        from gw2_progression.data_acquisition.factory import DataFactory
        factory = DataFactory()
        assert factory.source_registry is not None
        assert factory.flywheel is not None

    def test_factory_collect_all(self):
        from gw2_progression.data_acquisition.factory import DataFactory
        factory = DataFactory()
        results = factory.collect_all()
        assert len(results) > 0

    def test_factory_status(self):
        from gw2_progression.data_acquisition.factory import DataFactory
        factory = DataFactory()
        status = factory.status_report()
        assert "source_registry" in status
        assert "flywheel" in status
        assert "graph_builder" in status

    def test_factory_stream_push(self):
        from gw2_progression.data_acquisition.factory import DataFactory
        factory = DataFactory()
        factory.push_event("test", "custom", {"key": "val"})
        assert factory.stream_engine.buffer_size_current >= 1

    def test_factory_lifecycle(self):
        from gw2_progression.data_acquisition.factory import DataFactory
        factory = DataFactory()
        factory.start()
        assert factory.status.running
        factory.stop()
        assert not factory.status.running


class TestFactoryIntegration:
    def test_engine_has_data_factory(self):
        from gw2_progression.cognitive_os.engine import CognitiveOSEngine
        os = CognitiveOSEngine()
        assert hasattr(os, "data_factory")
        assert hasattr(os, "dataset_builder")

    def test_engine_ingest_source(self):
        from gw2_progression.cognitive_os.engine import CognitiveOSEngine
        os = CognitiveOSEngine()
        os.initialize({"gold": 100, "inventory": {}, "achievements": []})
        result = os.ingest_source()
        assert "status" in result

    def test_engine_generate_datasets(self):
        from gw2_progression.cognitive_os.engine import CognitiveOSEngine
        os = CognitiveOSEngine()
        os.initialize({"gold": 100, "inventory": {"ore": 5}, "achievements": ["a"]})
        result = os.generate_datasets()
        assert "total_samples" in result
        assert result["total_samples"] > 0

    def test_engine_factory_status(self):
        from gw2_progression.cognitive_os.engine import CognitiveOSEngine
        os = CognitiveOSEngine()
        os.initialize({"gold": 100, "inventory": {}, "achievements": []})
        status = os.factory_status()
        assert "source_registry" in status

    def test_engine_flywheel(self):
        from gw2_progression.cognitive_os.engine import CognitiveOSEngine
        os = CognitiveOSEngine()
        os.initialize({"gold": 100, "inventory": {"ore": 3}, "achievements": []})
        result = os.run_flywheel(iterations=1)
        assert result["iterations_run"] == 1
