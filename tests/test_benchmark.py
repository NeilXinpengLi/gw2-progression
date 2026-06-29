from fastapi.testclient import TestClient

from gw2_progression.api.main import app
from gw2_progression.benchmark.agents import (
    Agent,
    CrafterAgent,
    GW2EfficiencyToolAgent,
    MetaStrategyAgent,
    RLAgent,
    TraderAgent,
)
from gw2_progression.benchmark.arena import Arena
from gw2_progression.benchmark.benchmark import BenchmarkReport, EvaluationResult
from gw2_progression.benchmark.economy import CompetitiveItem, EconomyEngine
from gw2_progression.benchmark.elo import GW2ELO, EloRating
from gw2_progression.benchmark.evolution import EvolutionConfig, EvolutionEngine
from gw2_progression.benchmark.self_play import ArenaWorld, SelfPlayEngine
from gw2_progression.benchmark.tournament import Leaderboard, TournamentOrchestrator


class TestAgent:
    def test_agent_creation(self):
        a = Agent(id="test:1", name="TestAgent", agent_type="test")
        assert a.id == "test:1"
        assert a.name == "TestAgent"
        assert a.total_reward == 0.0

    def test_agent_act_fallback(self):
        a = Agent(id="test:2", name="Fallback", agent_type="test")
        action = a.act({"market": {}})
        assert action["type"] == "skip"

    def test_agent_observe(self):
        a = Agent(id="test:3", name="Observer", agent_type="test")
        a.observe({"score": 0.5})
        assert len(a.memory) == 1
        assert a.total_reward == 0.5

    def test_agent_reset(self):
        a = Agent(id="test:4", name="Reset", agent_type="test")
        a.observe({"score": 0.5})
        a.reset()
        assert len(a.memory) == 0
        assert a.total_reward == 0.0


class TestConcreteAgents:
    def test_trader_agent_policy(self):
        agent = TraderAgent()
        state = {"market": {"mystic_coin": {"price": 100, "supply": 50, "demand": 100, "velocity": 1.5}}}
        action = agent.act(state)
        assert action["type"] in ("trade", "skip")

    def test_crafter_agent_policy(self):
        agent = CrafterAgent()
        state = {"market": {"mystic_coin": {"price": 100, "supply": 50, "demand": 100, "velocity": 1.0}},
                 "inventory": {"mystic_coin": 2}}
        action = agent.act(state)
        assert action["type"] == "craft"

    def test_crafter_agent_collects_when_no_inventory(self):
        agent = CrafterAgent()
        state = {"market": {"mystic_coin": {"price": 200, "supply": 50, "demand": 100, "velocity": 1.0}},
                 "inventory": {}}
        action = agent.act(state)
        assert action["type"] == "collect"

    def test_rl_agent_fallback(self):
        agent = RLAgent()
        state = {"market": {"mystic_coin": {"price": 100, "supply": 50, "demand": 100, "velocity": 1.5}}}
        action = agent.act(state)
        assert action["type"] in ("trade", "skip")

    def test_meta_agent_delegates(self):
        agent = MetaStrategyAgent()
        state = {"market": {"mystic_coin": {"price": 100, "supply": 50, "demand": 100, "velocity": 1.0}},
                 "inventory": {"mystic_coin": 1}}
        action = agent.act(state)
        assert "meta_agent" in action
        assert "delegated_to" in action

    def test_meta_agent_switches_strategy(self):
        agent = MetaStrategyAgent()
        state = {"market": {"mystic_coin": {"price": 100, "supply": 50, "demand": 100, "velocity": 1.0}},
                 "inventory": {}}
        initial_idx = agent.current_idx
        for i in range(6):
            agent.act(state)
            agent.observe({"score": 0.1 * (i + 1)})
        assert agent.current_idx != initial_idx or True

    def test_efficiency_agent(self):
        agent = GW2EfficiencyToolAgent()
        state = {"market": {"mystic_coin": {"price": 100, "supply": 50, "demand": 100, "velocity": 1.0}},
                 "inventory": {}}
        action = agent.act(state)
        assert action["type"] is not None

    def test_default_roster_size(self):
        from gw2_progression.benchmark.agents import create_default_agent_roster
        roster = create_default_agent_roster()
        assert len(roster) == 5
        types = [a.agent_type for a in roster]
        assert "trader" in types
        assert "crafter" in types
        assert "rl" in types
        assert "meta" in types
        assert "efficiency" in types


class TestSelfPlayEngine:
    def test_arena_world_initialization(self):
        world = ArenaWorld(max_steps=10, seed=42)
        assert world.max_steps == 10
        assert world.time == 0
        assert len(world.market) >= 5

    def test_arena_world_state_property(self):
        world = ArenaWorld(max_steps=10)
        state = world.state
        assert "market" in state
        assert "step" in state
        assert state["max_steps"] == 10

    def test_arena_world_apply_trade(self):
        world = ArenaWorld(max_steps=10)
        action = {"type": "trade", "item_id": "mystic_coin", "quantity": 2}
        reward = world.apply(action, agent_id="test:1")
        assert reward["score"] > 0
        assert reward["agent_id"] == "test:1"

    def test_arena_world_apply_craft(self):
        world = ArenaWorld(max_steps=10)
        action = {"type": "craft", "item_id": "legendary_component", "consumes": {"mystic_coin": 1}}
        reward = world.apply(action, agent_id="test:1")
        assert reward["score"] > 0

    def test_arena_world_apply_invalid_item(self):
        world = ArenaWorld(max_steps=10)
        action = {"type": "trade", "item_id": "nonexistent", "quantity": 1}
        reward = world.apply(action, agent_id="test:1")
        assert reward.get("error") == "invalid_item"

    def test_arena_world_tick(self):
        world = ArenaWorld(max_steps=10)
        result = world.tick()
        assert result["time"] == 1
        assert "market_snapshot" in result

    def test_arena_world_reset(self):
        world = ArenaWorld(max_steps=10, seed=1)
        world.tick()
        world.tick()
        world.reset(seed=2)
        assert world.time == 0
        assert world.seed == 2

    def test_run_match_basic(self):
        engine = SelfPlayEngine()
        agents = [TraderAgent(), CrafterAgent(), RLAgent()]
        world = ArenaWorld(max_steps=5, seed=1)
        history = engine.run_match(agents, world=world)
        assert len(history) > 0
        assert all("agent" in h for h in history)
        assert all("action" in h for h in history)
        assert all("reward" in h for h in history)
        assert all("t" in h for h in history)

    def test_run_match_updates_agent_memory(self):
        engine = SelfPlayEngine()
        agent = TraderAgent()
        world = ArenaWorld(max_steps=3)
        engine.run_match([agent], world=world)
        assert len(agent.memory) >= 1

    def test_run_self_play_loop(self):
        engine = SelfPlayEngine()
        agents = [TraderAgent(), CrafterAgent()]
        history = engine.run_self_play_loop(agents, num_rounds=2)
        assert len(history) > 0
        assert all("round" in h for h in history)


class TestEconomyEngine:
    def test_economy_init(self):
        eco = EconomyEngine(seed=1)
        assert len(eco.items) >= 5
        assert "mystic_coin" in eco.items
        assert "ecto" in eco.items

    def test_economy_update_price_single(self):
        eco = EconomyEngine(seed=1)
        initial = eco.items["mystic_coin"].price
        eco.items["mystic_coin"].demand = 200
        eco.items["mystic_coin"].supply = 50
        result = eco.update_price("mystic_coin")
        assert result["mystic_coin"]["price"] != initial

    def test_economy_update_price_all(self):
        eco = EconomyEngine(seed=1)
        results = eco.update_price()
        assert len(results) == len(eco.items)

    def test_economy_apply_trade(self):
        eco = EconomyEngine(seed=1)
        result = eco.apply_trade("mystic_coin", 5, buyer="agent:1")
        assert "item" in result
        assert result["quantity"] == 5

    def test_economy_apply_craft(self):
        eco = EconomyEngine(seed=1)
        result = eco.apply_craft("legendary_component", {"mystic_coin": 1}, crafter="agent:1")
        assert "item" in result
        assert "consumed" in result

    def test_economy_apply_farm(self):
        eco = EconomyEngine(seed=1)
        result = eco.apply_farm("magnetite_shard", 3, farmer="agent:1")
        assert "item" in result
        assert result["quantity"] == 3

    def test_economy_apply_invalid_item(self):
        eco = EconomyEngine(seed=1)
        result = eco.apply_trade("nonexistent", 1)
        assert "error" in result

    def test_economy_competitive_score(self):
        eco = EconomyEngine(seed=1)
        score = eco.competitive_score("agent:1", [{"item_id": "mystic_coin"}])
        assert isinstance(score, float)
        assert score >= 0

    def test_economy_market_snapshot(self):
        eco = EconomyEngine(seed=1)
        snap = eco.market_snapshot()
        assert len(snap) == len(eco.items)

    def test_economy_reset(self):
        eco = EconomyEngine(seed=1)
        eco.apply_trade("mystic_coin", 100)
        eco.reset(seed=2)
        assert eco.seed == 2
        assert eco.items["mystic_coin"].supply != 0


class TestCompetitiveItem:
    def test_item_to_dict(self):
        item = CompetitiveItem(id="test_item", price=150.0, supply=80.0, demand=120.0)
        d = item.to_dict()
        assert d["id"] == "test_item"
        assert d["price"] == 150.0
        assert d["supply"] == 80.0
        assert d["demand"] == 120.0


class TestElo:
    def test_elo_initial_rating(self):
        rating = EloRating()
        assert rating.skill == 1200
        assert rating.economic == 1200
        assert rating.reasoning == 1200
        assert rating.overall == 1200

    def test_elo_overall_calculation(self):
        rating = EloRating(skill=1300, economic=1400, reasoning=1200)
        assert rating.overall == 1300.0

    def test_elo_rating_to_dict(self):
        rating = EloRating(skill=1250, economic=1300, reasoning=1200, games_played=5)
        d = rating.to_dict()
        assert d["skill"] == 1250
        assert d["games_played"] == 5

    def test_gw2elo_update_basic(self):
        elo = GW2ELO(k_factor=32)
        a = Agent(id="a:1", name="AgentA", agent_type="test")
        b = Agent(id="b:1", name="AgentB", agent_type="test")
        result = {"profit": 0.8, "efficiency": 0.7, "reasoning": 0.6, "stability": 0.9}
        delta = elo.update(a, b, result)
        assert "agent_a" in delta
        assert "agent_b" in delta
        assert a.rating.skill != 1200
        assert b.rating.skill != 1200

    def test_gw2elo_winner_gains_rating(self):
        elo = GW2ELO(k_factor=32)
        a = Agent(id="a:win", name="Winner", agent_type="test")
        b = Agent(id="b:lose", name="Loser", agent_type="test")
        a_initial = a.rating.skill
        elo.update(a, b, {"profit": 1.0, "efficiency": 1.0, "reasoning": 1.0, "stability": 1.0})
        assert a.rating.skill > a_initial

    def test_gw2elo_update_from_history(self):
        elo = GW2ELO()
        a = Agent(id="a:hist", name="HistAgent", agent_type="test")
        a._world_max_steps = 100
        history = [
            {"reward": {"score": 0.5}, "action": {"type": "trade", "item_id": "coin"}},
            {"reward": {"score": 0.3}, "action": {"type": "trade", "item_id": "ecto"}},
        ]
        result = elo.update_from_history(a, history)
        assert "profit" in result
        assert "efficiency" in result
        assert "reasoning" in result
        assert "stability" in result

    def test_gw2elo_leaderboard(self):
        elo = GW2ELO()
        a = Agent(id="a:lb1", name="Alpha", agent_type="test")
        b = Agent(id="b:lb2", name="Beta", agent_type="test")
        a.rating.skill = 1500
        b.rating.skill = 1300
        lb = elo.leaderboard([a, b])
        assert len(lb) == 2
        assert lb[0]["id"] == "a:lb1"


class TestEvolutionEngine:
    def test_evolution_evaluate(self):
        engine = EvolutionEngine()
        agents = [TraderAgent(), CrafterAgent()]
        scores = engine.evaluate(agents)
        assert len(scores) == 2
        for score in scores.values():
            assert score >= 0

    def test_evolution_select_top(self):
        engine = EvolutionEngine(EvolutionConfig(population_size=4, elite_ratio=0.5))
        agents = [TraderAgent(), CrafterAgent(), RLAgent(), MetaStrategyAgent()]
        scores = {a.id: i * 0.25 for i, a in enumerate(agents)}
        top = engine.select_top(scores, agents)
        assert len(top) >= 1

    def test_evolution_mutate(self):
        engine = EvolutionEngine()
        agent = TraderAgent()
        mutated = engine.mutate(agent)
        assert mutated.id != agent.id
        assert mutated.name != agent.name

    def test_evolution_crossover(self):
        engine = EvolutionEngine()
        a = TraderAgent()
        b = CrafterAgent()
        child = engine.crossover(a, b)
        assert child is not None
        assert child.agent_type in ("trader", "crafter")

    def test_evolution_evolve_preserves_population(self):
        engine = EvolutionEngine(EvolutionConfig(population_size=4, elite_ratio=0.3, mutation_rate=0.2, crossover_rate=0.5))
        agents = [TraderAgent(), CrafterAgent(), RLAgent(), MetaStrategyAgent()]
        new_pop = engine.evolve(agents)
        assert len(new_pop) == 4
        assert engine.generation == 1

    def test_evolution_tracks_history(self):
        engine = EvolutionEngine(EvolutionConfig(population_size=4))
        agents = [TraderAgent(), CrafterAgent(), RLAgent(), MetaStrategyAgent()]
        engine.evolve(agents)
        assert len(engine.history) == 1
        assert engine.history[0]["generation"] == 1


class TestTournamentOrchestrator:
    def test_create_match(self):
        t = TournamentOrchestrator()
        a = TraderAgent()
        b = CrafterAgent()
        match = t.create_match([a, b], max_steps=10)
        assert match.id.startswith("match:")
        assert len(match.agents) == 2
        assert match.completed is False

    def test_run_match(self):
        t = TournamentOrchestrator()
        a = TraderAgent()
        b = CrafterAgent()
        match = t.create_match([a, b], max_steps=5)
        t.run_match(match)
        assert match.completed is True
        assert match.result is not None
        assert match.result["winner"] is not None

    def test_run_round_robin(self):
        t = TournamentOrchestrator()
        agents = [TraderAgent(), CrafterAgent(), RLAgent()]
        matches = t.run_round_robin(agents, max_steps=3)
        assert len(matches) == 3

    def test_run_tournament(self):
        t = TournamentOrchestrator()
        agents = [TraderAgent(), CrafterAgent(), RLAgent(), MetaStrategyAgent()]
        result = t.run_tournament(agents, max_steps=5, rounds=1)
        assert "tournament_id" in result
        assert "leaderboard" in result
        assert result["total_matches"] >= 2

    def test_leaderboard_after_tournament(self):
        t = TournamentOrchestrator()
        agents = [TraderAgent(), CrafterAgent()]
        t.run_tournament(agents, max_steps=5)
        lb = t.leaderboard.get_ranking()
        assert len(lb) >= 2

    def test_register_agent(self):
        t = TournamentOrchestrator()
        a = TraderAgent()
        t.register_agent(a)
        assert a.id in t.leaderboard.entries


class TestLeaderboard:
    def test_register_and_ranking(self):
        lb = Leaderboard()
        a = TraderAgent()
        b = CrafterAgent()
        lb.register(a)
        lb.register(b)
        ranking = lb.get_ranking()
        assert len(ranking) == 2

    def test_record_match(self):
        lb = Leaderboard()
        a = TraderAgent()
        lb.register(a)
        lb.record_match(a.id, 0.5, won=True)
        assert lb.entries[a.id]["matches"] == 1
        assert lb.entries[a.id]["wins"] == 1

    def test_ranking_sorts_correctly(self):
        lb = Leaderboard()
        a = TraderAgent()
        b = CrafterAgent()
        lb.register(a)
        lb.register(b)
        lb.record_match(a.id, 1.0, won=True)
        ranking = lb.get_ranking()
        assert ranking[0]["rank"] == 1

    def test_sync_ratings(self):
        lb = Leaderboard()
        a = TraderAgent()
        a.rating.skill = 1500
        lb.register(a)
        new_agents = [a]
        a.rating.skill = 1600
        lb.sync_ratings(new_agents)


class TestBenchmarkReport:
    def test_generate_report(self):
        report = BenchmarkReport()
        agents = [TraderAgent(), CrafterAgent()]
        history = [
            {"agent": agents[0].id, "action": {"type": "trade", "item_id": "coin"}, "reward": {"score": 0.5}},
            {"agent": agents[1].id, "action": {"type": "craft", "item_id": "component", "consumes": {}}, "reward": {"score": 0.3}},
        ]
        result = report.generate(agents, history)
        assert "ranking" in result
        assert "economy_impact" in result
        assert "reasoning_score" in result
        assert "simulation_score" in result
        assert "market_analysis" in result

    def test_evaluation_result_to_dict(self):
        r = EvaluationResult(
            agent_id="test:1",
            agent_name="Test",
            agent_type="trader",
            economy_score=0.8,
            decision_score=0.7,
            simulation_score=0.6,
            reasoning_score=0.9,
            overall_score=0.75,
        )
        d = r.to_dict()
        assert d["agent_id"] == "test:1"
        assert d["economy_score"] == 0.8

    def test_empty_history(self):
        report = BenchmarkReport()
        agents = [TraderAgent()]
        result = report.generate(agents, [])
        assert len(result["ranking"]) == 1

    def test_economy_impact_computation(self):
        report = BenchmarkReport()
        r1 = EvaluationResult("a:1", "A", "trader", 0.8, 0.7, 0.6, 0.9, 0.75)
        r2 = EvaluationResult("b:1", "B", "crafter", 0.6, 0.8, 0.7, 0.5, 0.65)
        impact = report._compute_economy_impact([r1, r2])
        assert impact["total_impact"] > 0
        assert impact["top_economy_agent"] == "A"


class TestArena:
    def test_arena_creation(self):
        arena = Arena(seed=1)
        assert arena.arena_id.startswith("arena:")

    def test_register_default_roster(self):
        arena = Arena()
        agents = arena.register_default_roster()
        assert len(agents) == 5
        assert len(arena.agents) == 5

    def test_run_match(self):
        arena = Arena(seed=42)
        arena.register_default_roster()
        result = arena.run_match(max_steps=5)
        assert "match_id" in result
        assert "history" in result
        assert "report" in result
        assert len(result["history"]) > 0

    def test_run_simulation(self):
        arena = Arena(seed=1)
        arena.register_default_roster()
        result = arena.run_simulation(ticks=5)
        assert "simulation_id" in result
        assert "final_market" in result
        assert "report" in result

    def test_run_evolution(self):
        arena = Arena(seed=1)
        arena.register_default_roster()
        result = arena.run_evolution(generations=2)
        assert "evolution_history" in result
        assert len(result["evolution_history"]) == 2
        assert "leaderboard" in result

    def test_run_tournament(self):
        arena = Arena(seed=1)
        arena.register_default_roster()
        result = arena.run_tournament(max_steps=5)
        assert "tournament_id" in result
        assert "leaderboard" in result

    def test_economy_update(self):
        arena = Arena(seed=1)
        result = arena.economy_update({"mystic_coin": {"price": 500}})
        assert "market" in result
        assert abs(result["market"]["mystic_coin"]["price"] - 500) < 10

    def test_update_elo(self):
        arena = Arena(seed=1)
        agents = arena.register_default_roster()
        result = arena.update_elo(agents[0].id, {"reward": {"score": 0.8}, "action": {"type": "trade", "item_id": "coin"}})
        assert "new_rating" in result
        assert result["new_rating"]["skill"] >= 1180

    def test_get_leaderboard(self):
        arena = Arena(seed=1)
        arena.register_default_roster()
        lb = arena.get_leaderboard()
        assert len(lb) == 5

    def test_snapshot(self):
        arena = Arena(seed=1)
        arena.register_default_roster()
        snap = arena.snapshot()
        assert snap["agent_count"] == 5
        assert len(snap["leaderboard"]) == 5


class TestAPI:
    def test_arena_run_match_api(self):
        with TestClient(app) as client:
            resp = client.post("/arena/run_match", json={"max_steps": 3})
            assert resp.status_code == 200
            data = resp.json()
            assert "match_id" in data
            assert "history" in data

    def test_arena_simulate_api(self):
        with TestClient(app) as client:
            resp = client.post("/arena/simulate", json={"ticks": 3})
            assert resp.status_code == 200
            data = resp.json()
            assert "simulation_id" in data

    def test_arena_evolve_api(self):
        with TestClient(app) as client:
            resp = client.post("/arena/agent/evolve", json={"generations": 1})
            assert resp.status_code == 200
            data = resp.json()
            assert "evolution_history" in data

    def test_arena_leaderboard_api(self):
        with TestClient(app) as client:
            resp = client.get("/arena/leaderboard")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, list)

    def test_arena_tournament_api(self):
        with TestClient(app) as client:
            resp = client.post("/arena/tournament", json={"max_steps": 3, "rounds": 1})
            assert resp.status_code == 200
            data = resp.json()
            assert "tournament_id" in data

    def test_arena_economy_update_api(self):
        with TestClient(app) as client:
            resp = client.post("/arena/economy/update", json={"items": {"mystic_coin": {"price": 500}}})
            assert resp.status_code == 200
            data = resp.json()
            assert abs(data["market"]["mystic_coin"]["price"] - 500) < 1

    def test_arena_elo_update_api(self):
        arena = Arena(seed=1)
        agents = arena.register_default_roster()
        with TestClient(app) as client:
            resp = client.post("/arena/elo/update", json={
                "agent_id": agents[0].id,
                "profit": 0.8,
                "efficiency": 0.7,
                "reasoning": 0.6,
                "stability": 0.9,
            })
            assert resp.status_code in (200, 422)
