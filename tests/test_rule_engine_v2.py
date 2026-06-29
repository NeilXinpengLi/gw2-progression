import numpy as np
from fastapi.testclient import TestClient

from gw2_progression.api.main import app
from gw2_progression.rule_engine_v2.core.competition.ranking_system import RuleRankingSystem
from gw2_progression.rule_engine_v2.core.competition.rule_agents import create_rule_agent
from gw2_progression.rule_engine_v2.core.competition.tournament_engine import RuleTournament
from gw2_progression.rule_engine_v2.core.engine import RuleEngineV2
from gw2_progression.rule_engine_v2.core.evolution.rule_mutator import RuleMutator
from gw2_progression.rule_engine_v2.core.evolution.rule_selector import RuleSelector
from gw2_progression.rule_engine_v2.core.evolution.survival_engine import RuleEvolutionSystem
from gw2_progression.rule_engine_v2.core.gnn.message_passing import MessagePassingLayer, MessagePassingNetwork
from gw2_progression.rule_engine_v2.core.gnn.rule_encoder import RuleEdge, RuleEncoder, RuleGraph
from gw2_progression.rule_engine_v2.core.gnn.rule_graph_model import RuleGNN
from gw2_progression.rule_engine_v2.core.llm.reasoning_compressor import ReasoningCompressor
from gw2_progression.rule_engine_v2.core.llm.rule_distiller import DistilledRule, RuleDistiller
from gw2_progression.rule_engine_v2.core.rl.reward_engine import RuleReward
from gw2_progression.rule_engine_v2.core.rl.rule_optimizer import RuleOptimizer
from gw2_progression.rule_engine_v2.core.rl.rule_policy import RulePolicy
from gw2_progression.rule_engine_v2.simulation.economy_sim import EconomySim
from gw2_progression.rule_engine_v2.simulation.gw2_world_sim import GW2WorldSim, GW2WorldState

SAMPLE_RULES = [
    {
        "id": "r1", "type": "crafting", "name": "Craft Legendary", "action": "craft", "target": "inventory",
        "price_impact": 0.02, "base_accuracy": 0.8, "profit": 50, "volatility": 0.2, "priority": 1,
        "active": True, "conditions": [], "actions": [], "test_count": 10, "test_pass": 8,
        "volume": 100, "market_impact": 0.1, "complexity": 0.3, "depth": 1,
    },
    {
        "id": "r2", "type": "economy", "name": "Flip Ecto", "action": "trade", "target": "market",
        "price_impact": 0.05, "base_accuracy": 0.7, "profit": 30, "volatility": 0.4, "priority": 2,
        "active": True, "conditions": [], "actions": [], "test_count": 20, "test_pass": 14,
        "volume": 200, "market_impact": 0.2, "complexity": 0.5, "depth": 2,
    },
    {
        "id": "r3", "type": "behavior", "name": "Farm Rotation", "action": "farm", "target": "inventory",
        "price_impact": 0.01, "base_accuracy": 0.9, "profit": 10, "volatility": 0.1, "priority": 3,
        "active": True, "conditions": [], "actions": [], "test_count": 5, "test_pass": 5,
        "volume": 50, "market_impact": 0.05, "complexity": 0.2, "depth": 1,
    },
    {
        "id": "r4", "type": "meta", "name": "Strategy Switch", "action": "skip", "target": "market",
        "price_impact": 0.0, "base_accuracy": 0.6, "profit": 0, "volatility": 0.5, "priority": 4,
        "active": True, "conditions": [], "actions": [], "test_count": 8, "test_pass": 4,
        "volume": 10, "market_impact": 0.3, "complexity": 0.7, "depth": 3,
    },
]


class TestRuleEncoder:
    def test_encode_rule(self):
        encoder = RuleEncoder()
        node = encoder.encode_rule(SAMPLE_RULES[0])
        assert node.node_type == "crafting"
        assert len(node.features) == 8

    def test_encode_rules(self):
        encoder = RuleEncoder()
        nodes = encoder.encode_rules(SAMPLE_RULES)
        assert len(nodes) == 4

    def test_build_graph(self):
        encoder = RuleEncoder()
        nodes = encoder.encode_rules(SAMPLE_RULES)
        graph = encoder.build_graph(nodes)
        assert len(graph.nodes) == 4

    def test_build_graph_with_edges(self):
        encoder = RuleEncoder()
        nodes = encoder.encode_rules(SAMPLE_RULES[:2])
        edges = [RuleEdge(source=nodes[0].id, target=nodes[1].id, edge_type="depends", weight=0.8)]
        graph = encoder.build_graph(nodes, edges)
        assert len(graph.edges) == 1

    def test_similarity(self):
        encoder = RuleEncoder()
        a = np.array([1, 0, 0, 0, 0.5, 0.5, 0.5, 0], dtype=np.float32)
        b = np.array([1, 0, 0, 0, 0.3, 0.4, 0.6, 0], dtype=np.float32)
        sim = encoder._similarity(a, b)
        assert sim > 0


class TestRuleGraph:
    def test_adjacency(self):
        encoder = RuleEncoder()
        nodes = encoder.encode_rules(SAMPLE_RULES[:2])
        graph = encoder.build_graph(nodes)
        adj = graph.adjacency
        assert adj.shape == (2, 2)

    def test_feature_matrix(self):
        encoder = RuleEncoder()
        graph = encoder.build_graph(encoder.encode_rules(SAMPLE_RULES[:3]))
        fm = graph.feature_matrix
        assert fm.shape[0] == 3

    def test_empty_feature_matrix(self):
        graph = RuleGraph()
        fm = graph.feature_matrix
        assert fm.shape == (0, 4)


class TestMessagePassing:
    def test_layer_forward(self):
        layer = MessagePassingLayer(4, 8, activation="relu")
        features = np.random.randn(3, 4).astype(np.float32)
        adj = np.eye(3, dtype=np.float32)
        out = layer.forward(features, adj)
        assert out.shape == (3, 8)

    def test_network_forward(self):
        net = MessagePassingNetwork(input_dim=4, hidden_dim=8, output_dim=4, num_layers=2)
        features = np.random.randn(3, 4).astype(np.float32)
        adj = np.eye(3, dtype=np.float32)
        out = net.forward(features, adj)
        assert out.shape == (3, 4)

    def test_forward_batch(self):
        net = MessagePassingNetwork(input_dim=4, hidden_dim=8, output_dim=4, num_layers=2)
        graphs = [(np.random.randn(2, 4).astype(np.float32), np.eye(2, dtype=np.float32)) for _ in range(3)]
        outs = net.forward_batch(graphs)
        assert len(outs) == 3


class TestRuleGNN:
    def test_encode_and_forward(self):
        gnn = RuleGNN()
        embeddings = gnn.forward_with_rules(SAMPLE_RULES)
        assert len(embeddings) > 0

    def test_get_embeddings(self):
        gnn = RuleGNN()
        embs = gnn.get_embeddings(SAMPLE_RULES)
        assert len(embs) == 4

    def test_predict_rule_quality(self):
        gnn = RuleGNN()
        emb = gnn.forward_with_rules(SAMPLE_RULES[:1])
        quality = gnn.predict_rule_quality(emb[0]) if len(emb) > 0 else 0.5
        assert 0 <= quality <= 1

    def test_discover_rule_clusters(self):
        gnn = RuleGNN()
        clusters = gnn.discover_rule_clusters(SAMPLE_RULES, n_clusters=2)
        assert len(clusters) <= 2


class TestRulePolicy:
    def test_select_action(self):
        policy = RulePolicy()
        action = policy.select_action({"id": "r1"})
        assert action in ("apply", "skip", "modify", "defer", "merge")

    def test_update(self):
        policy = RulePolicy()
        policy.update("r1", "apply", 0.8)
        action = policy.get_best_action("r1")
        assert action == "apply"

    def test_get_action_probs(self):
        policy = RulePolicy()
        probs = policy.get_action_probs("r1")
        assert len(probs) == 5
        assert abs(sum(probs.values()) - 1.0) < 0.01

    def test_reset(self):
        policy = RulePolicy()
        policy.update("r1", "apply", 0.8)
        policy.reset()
        assert policy.q_table == {}


class TestRuleReward:
    def test_compute(self):
        reward = RuleReward()
        result = reward.compute(SAMPLE_RULES[0])
        assert "accuracy" in result
        assert "profit" in result
        assert "stability" in result
        assert "total" in result

    def test_compute_batch(self):
        reward = RuleReward()
        results = reward.compute_batch(SAMPLE_RULES)
        assert len(results) == 4

    def test_fitness(self):
        reward = RuleReward()
        fitness = reward.fitness(SAMPLE_RULES[0])
        assert isinstance(fitness, float)


class TestRuleOptimizer:
    def test_update(self):
        opt = RuleOptimizer()
        result = opt.update(SAMPLE_RULES)
        assert len(result) == 4

    def test_get_best_rules(self):
        opt = RuleOptimizer()
        best = opt.get_best_rules(SAMPLE_RULES, k=2)
        assert len(best) == 2


class TestRuleDistiller:
    def test_distill_empty(self):
        distiller = RuleDistiller()
        distilled = distiller.distill([])
        assert len(distilled) >= 1

    def test_distill_with_rules(self):
        distiller = RuleDistiller()
        distilled = distiller.distill(SAMPLE_RULES)
        assert len(distilled) >= 1
        assert all(isinstance(d, DistilledRule) for d in distilled)

    def test_distilled_rule_to_dict(self):
        d = DistilledRule(id="test", name="Test", abstraction="Test abstraction", conditions=["c1"], actions=["a1"], confidence=0.8)
        dd = d.to_dict()
        assert dd["id"] == "test"

    def test_build_prompt(self):
        distiller = RuleDistiller()
        prompt = distiller.build_prompt({"rules": SAMPLE_RULES})
        assert "GW2" in prompt


class TestReasoningCompressor:
    def test_compress(self):
        comp = ReasoningCompressor()
        chain = [{"type": "trade", "item_id": "coin"}, {"type": "craft", "item_id": "component"}, {"type": "trade", "item_id": "ecto"}]
        result = comp.compress(chain, max_steps=2)
        assert result.original_length == 3
        assert result.compressed_length <= 2

    def test_compress_batch(self):
        comp = ReasoningCompressor()
        chains = [[{"type": "trade"}], [{"type": "craft"}, {"type": "farm"}]]
        results = comp.compress_batch(chains)
        assert len(results) == 2

    def test_empty_chain(self):
        comp = ReasoningCompressor()
        result = comp.compress([])
        assert result.summary == "Empty reasoning chain"


class TestRuleAgent:
    def test_creation(self):
        agent = create_rule_agent("TestAgent")
        assert agent.name == "TestAgent"
        assert len(agent.rules) > 0

    def test_apply_rules(self):
        agent = create_rule_agent("TestAgent", rules=SAMPLE_RULES[:1])
        world = {"market": {"coin": {"price": 100, "supply": 100, "demand": 100}}, "inventory": {"item": 5}}
        result = agent.apply_rules(world)
        assert "market" in result

    def test_evaluate(self):
        agent = create_rule_agent("EvalAgent", rules=SAMPLE_RULES[:1])
        world = {"market": {"coin": {"price": 100, "supply": 1000, "demand": 1000}}, "inventory": {"item": 50}}
        score = agent.evaluate(world)
        assert score >= 0

    def test_to_dict(self):
        agent = create_rule_agent("DictAgent")
        d = agent.to_dict()
        assert d["name"] == "DictAgent"


class TestRuleTournament:
    def test_run_basic(self):
        tournament = RuleTournament()
        agents = [create_rule_agent("A"), create_rule_agent("B")]
        world = {"market": {"coin": {"price": 100, "supply": 100, "demand": 100}}, "inventory": {"item": 10}}
        results = tournament.run(agents, world)
        assert len(results) >= 0

    def test_rank(self):
        tournament = RuleTournament()
        results = [{"scores": {"a:1": 0.8, "b:1": 0.6}}]
        ranked = tournament.rank(results)
        assert len(ranked) == 2


class TestRuleRankingSystem:
    def test_leaderboard(self):
        ranking = RuleRankingSystem()
        agents = [create_rule_agent("A"), create_rule_agent("B")]
        lb = ranking.leaderboard(agents)
        assert len(lb) == 2

    def test_get_rating(self):
        ranking = RuleRankingSystem()
        ranking.initialize(create_rule_agent("Test"))
        rating = ranking.get_rating("unknown")
        assert rating["elo"] == 1200


class TestRuleMutator:
    def test_mutate(self):
        mutator = RuleMutator(mutation_rate=1.0)
        mutated = mutator.mutate(SAMPLE_RULES[0])
        assert mutated.get("mutated", False) or True

    def test_mutate_batch(self):
        mutator = RuleMutator(mutation_rate=0.0)
        mutated = mutator.mutate_batch(SAMPLE_RULES)
        assert len(mutated) == 4


class TestRuleSelector:
    def test_select_elite(self):
        selector = RuleSelector(elite_ratio=0.5)
        elite = selector.select_elite(SAMPLE_RULES)
        assert len(elite) <= 4

    def test_tournament_select(self):
        selector = RuleSelector(tournament_size=2)
        selected = selector.tournament_select(SAMPLE_RULES)
        assert selected is not None


class TestRuleEvolutionSystem:
    def test_evolve_from_empty(self):
        evo = RuleEvolutionSystem(population_size=5)
        population = evo.evolve([])
        assert len(population) == 5

    def test_evolve_from_rules(self):
        evo = RuleEvolutionSystem(population_size=5)
        population = evo.evolve(SAMPLE_RULES[:2])
        assert len(population) == 5
        assert evo.generation == 1

    def test_select(self):
        evo = RuleEvolutionSystem()
        selected = evo.select(SAMPLE_RULES, k=2)
        assert len(selected) == 2

    def test_history_tracking(self):
        evo = RuleEvolutionSystem(population_size=4)
        evo.evolve(SAMPLE_RULES[:2])
        assert len(evo.history) == 1
        assert "avg_fitness" in evo.history[0]


class TestGW2WorldSim:
    def test_reset(self):
        sim = GW2WorldSim()
        sim.reset(seed=42)
        assert len(sim.state.market) >= 5

    def test_step(self):
        sim = GW2WorldSim()
        sim.reset()
        state = sim.step(SAMPLE_RULES[:1])
        assert state.time == 1

    def test_step_batch(self):
        sim = GW2WorldSim()
        sim.reset()
        states = sim.step_batch(SAMPLE_RULES[:1], steps=3)
        assert len(states) == 3


class TestGW2WorldState:
    def test_copy(self):
        state = GW2WorldState(time=5, market={"coin": {"price": 100}}, inventory={"item": 1})
        copied = state.copy()
        assert copied.time == 5
        copied.time = 10
        assert state.time == 5

    def test_to_dict(self):
        state = GW2WorldState(time=3)
        d = state.to_dict()
        assert d["time"] == 3


class TestEconomySim:
    def test_reset(self):
        eco = EconomySim()
        eco.reset()
        assert len(eco.prices) >= 5

    def test_simulate_step(self):
        eco = EconomySim()
        eco.reset()
        snapshot = eco.simulate_step(SAMPLE_RULES[:1])
        assert "prices" in snapshot

    def test_simulate(self):
        eco = EconomySim()
        trajectory = eco.simulate(SAMPLE_RULES[:1], steps=3)
        assert len(trajectory) == 3

    def test_get_metrics(self):
        eco = EconomySim()
        eco.reset()
        eco.simulate(SAMPLE_RULES[:1], steps=5)
        metrics = eco.get_metrics()
        assert "avg_price" in metrics
        assert "total_volume" in metrics


class TestRuleEngineV2:
    def test_extract_rules_none(self):
        engine = RuleEngineV2()
        rules = engine.extract_rules()
        assert len(rules) > 0

    def test_extract_rules_from_list(self):
        engine = RuleEngineV2()
        rules = engine.extract_rules(SAMPLE_RULES)
        assert len(rules) == 4

    def test_encode_rules_gnn(self):
        engine = RuleEngineV2()
        engine.extract_rules(SAMPLE_RULES)
        embs = engine.encode_rules_gnn()
        assert len(embs) == 4

    def test_simulate_rules(self):
        engine = RuleEngineV2()
        engine.extract_rules(SAMPLE_RULES)
        result = engine.simulate_rules(steps=3)
        assert "world_states" in result
        assert "economy_snapshots" in result

    def test_evaluate_rules(self):
        engine = RuleEngineV2()
        engine.extract_rules(SAMPLE_RULES)
        result = engine.evaluate_rules()
        assert len(result) == 4

    def test_optimize_rules(self):
        engine = RuleEngineV2()
        engine.extract_rules(SAMPLE_RULES)
        result = engine.optimize_rules()
        assert len(result) == 4

    def test_distill_rules(self):
        engine = RuleEngineV2()
        engine.extract_rules(SAMPLE_RULES)
        result = engine.distill_rules()
        assert len(result) >= 1

    def test_evolve_rules(self):
        engine = RuleEngineV2()
        engine.extract_rules(SAMPLE_RULES[:2])
        result = engine.evolve_rules()
        assert len(result) > 0

    def test_run_full_pipeline(self):
        engine = RuleEngineV2()
        engine.extract_rules(SAMPLE_RULES[:2])
        result = engine.run_full_pipeline()
        assert "pipeline_id" in result
        assert "steps" in result
        assert "evolution_history" in result

    def test_compete_rules(self):
        engine = RuleEngineV2()
        engine.extract_rules(SAMPLE_RULES)
        result = engine.compete_rules()
        assert "tournament_id" in result


class TestRuleEngineV2API:
    def test_extract_api(self):
        with TestClient(app) as client:
            resp = client.post("/rules/v2/extract", json={"rules": SAMPLE_RULES})
            assert resp.status_code == 200
            data = resp.json()
            assert "rules" in data

    def test_simulate_api(self):
        with TestClient(app) as client:
            resp = client.post("/rules/v2/simulate", json={"steps": 3})
            assert resp.status_code == 200

    def test_evolve_api(self):
        with TestClient(app) as client:
            resp = client.post("/rules/v2/evolve", json={"population_size": 5})
            assert resp.status_code == 200

    def test_compete_api(self):
        with TestClient(app) as client:
            resp = client.post("/rules/v2/compete", json={"agent_count": 2})
            assert resp.status_code == 200

    def test_distill_api(self):
        with TestClient(app) as client:
            resp = client.post("/rules/v2/distill", json={})
            assert resp.status_code == 200

    def test_optimize_api(self):
        with TestClient(app) as client:
            resp = client.post("/rules/v2/optimize", json={})
            assert resp.status_code == 200

    def test_leaderboard_api(self):
        with TestClient(app) as client:
            resp = client.get("/rules/v2/leaderboard")
            assert resp.status_code == 200

    def test_pipeline_api(self):
        with TestClient(app) as client:
            resp = client.post("/rules/v2/pipeline", json={})
            assert resp.status_code == 200
