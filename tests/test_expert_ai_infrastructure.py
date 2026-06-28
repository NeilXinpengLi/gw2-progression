"""Tests for GW2 Expert AI training infrastructure."""

from pathlib import Path

from fastapi.testclient import TestClient

from gw2_progression.api.main import app
from gw2_progression.expert_ai.adapters import account_contents_to_runtime_payload
from gw2_progression.expert_ai.core import ExpertAISystem
from gw2_progression.expert_ai.persistence import ExpertAIPersistence, ExpertAIServiceConfig, Neo4jGraphAdapter, PostgresStateAdapter, RedisQueueAdapter
from gw2_progression.expert_ai.training import build_dataset
from gw2_progression.expert_ai.worker import consume_once, run_once


def test_graph_compile_from_domain_yaml():
    system = ExpertAISystem()
    compiled = system.compile_graph(file_path="domain_graph.yaml")

    assert "quest" in compiled["errors"][0]
    assert "account_snapshot" in compiled["dgsk"]["nodes"]
    assert "owns" in compiled["oosk"]["relation_types"]
    assert "account_asset_value" in compiled["bors"]


def test_runtime_action_snapshot_and_reasoning_trace():
    system = ExpertAISystem()
    entity_result = system.runtime.execute({"type": "add_entity", "entity": {"id": "item:1", "type": "Item", "properties": {"name": "Gold"}}})
    relation_result = system.runtime.execute({"type": "add_relation", "relation": {"source": "account:1", "target": "item:1", "relation_type": "owns"}})

    assert entity_result["status"] == "completed"
    assert relation_result["status"] == "completed"
    trace = system.reasoning.trace("account:1")
    assert trace["visited"] == ["account:1", "item:1"]


def test_runtime_rollback_restores_previous_graph_state():
    system = ExpertAISystem()
    baseline = system.runtime.snapshot()

    result = system.runtime.execute({"type": "add_entity", "entity": {"id": "volatile:item", "type": "Item"}})
    assert result["status"] == "completed"
    assert system.runtime.get_entity("volatile:item") is not None

    assert system.runtime.rollback(baseline.id) is True
    assert system.runtime.get_entity("volatile:item") is None


def test_reasoning_path_and_missing_goal_decisions():
    system = ExpertAISystem()
    system.runtime.add_entity({"id": "account:path", "type": "account_snapshot"})
    system.runtime.add_entity({"id": "goal:path", "type": "legendary_goal"})
    system.runtime.add_relation({"source": "account:path", "target": "goal:path", "relation_type": "pursues"})

    found = system.reasoning.analyze(start="account:path", goal="goal:path")
    missing = system.reasoning.analyze(start="account:path", goal="goal:missing")

    assert found["decision"] == "REVIEW"
    assert [step["node"] for step in found["reasoning_chain"]] == ["account:path", "goal:path"]
    assert missing["decision"] == "REJECT"
    assert missing["reasoning_chain"] == []


def test_account_contents_adapter_builds_runtime_payload():
    class Contents:
        account_name = "Adapter.1234"
        account_world = 1001
        account_created = "2024-01-01T00:00:00Z"
        account_age_hours = 10
        wallet = [{"id": 1, "value": 12345}]
        materials = [{"id": 19721, "count": 2}]
        bank = []
        shared_inventory = []
        tradingpost_buys = []
        tradingpost_sells = []
        unlocked_skins = [1, 2]
        unlocked_dyes = []
        unlocked_minis = []
        unlocked_finishers = []
        daily_ap = 10
        monthly_ap = 1
        wvw_rank = 5
        fractal_level = 9
        builds = []
        masteries = []
        account = {"guilds": []}
        characters = [{
            "name": "Adapter Char",
            "profession": "Guardian",
            "race": "Human",
            "level": 80,
            "age": 3600,
            "bags": [{"inventory": [{"id": 19721, "count": 1}]}],
            "equipment": [],
        }]

    payload = account_contents_to_runtime_payload(Contents(), item_limit=10)

    assert payload["summary"]["account_id"] == "account:Adapter.1234"
    assert any(e["type"] == "Character" for e in payload["entities"])
    assert any(r["relation_type"] == "owns" for r in payload["relations"])


def test_account_contents_adapter_honors_item_limit_and_dedupes_locations():
    class Contents:
        account_name = "Limit.1234"
        account_world = 1001
        account_created = "2024-01-01T00:00:00Z"
        account_age_hours = 10
        wallet = []
        materials = [{"id": 19721, "count": 2}, {"id": 19722, "count": 3}]
        bank = [{"id": 19723, "count": 4}]
        shared_inventory = []
        tradingpost_buys = []
        tradingpost_sells = []
        unlocked_skins = []
        unlocked_dyes = []
        unlocked_minis = []
        unlocked_finishers = []
        daily_ap = 0
        monthly_ap = 0
        wvw_rank = 0
        fractal_level = 0
        builds = []
        masteries = []
        account = {"guilds": []}
        characters = []

    payload = account_contents_to_runtime_payload(Contents(), item_limit=1)
    item_entities = [entity for entity in payload["entities"] if entity["type"] == "Item"]
    location_entities = [entity for entity in payload["entities"] if entity["type"] == "StorageLocation"]

    assert payload["summary"]["items_included"] == 1
    assert payload["summary"]["items_total"] == 3
    assert len(item_entities) == 1
    assert len({entity["id"] for entity in location_entities}) == len(location_entities)


def test_decision_economy_meta_plan_memory_and_training():
    system = ExpertAISystem()

    decision = system.evaluate_decision({
        "decision_type": "approve_recommendation",
        "factors": [{"name": "confidence", "value": 0.9, "weight": 1, "impact": "positive"}],
    })
    economy = system.economy.simulate([{"item_id": 19721, "price": 100, "supply": 50, "demand": 120}])
    meta = system.meta.analyze_build({"gear_completion_percent": 90, "role": "dps", "review_status": "reviewed"})
    plan = system.planner.generate([{"name": "Legendary", "missing_cost": 100, "priority": "high", "progress": 0.4}], {"budget": 200})
    memory = system.memory.append({"type": "episodic", "action": "simulate", "outcome": "ok"})
    dataset = build_dataset({"graph": {"nodes": [{"id": "n1"}], "edges": []}})

    assert decision["decision"] == "APPROVE"
    assert economy["items"][0]["liquidity"] == "high"
    assert meta["raid_viability"] == "ready"
    assert plan["plan"][0]["decision"] == "APPROVE"
    assert memory["id"]
    assert dataset["examples"][0]["decision"]["status"] == "REVIEW"


def test_decision_economy_meta_and_memory_edge_cases():
    system = ExpertAISystem()

    blocked = system.evaluate_decision({
        "decision_type": "approve_recommendation",
        "factors": [
            {"name": "confidence", "value": 0.95, "weight": 1, "impact": "positive"},
            {"name": "api_key_leak", "value": 0.95, "weight": 1, "impact": "negative"},
        ],
    })
    economy = system.economy.simulate([{"item_id": 1, "price": 100, "supply": 1000, "demand": 0}])
    meta = system.meta.analyze_build({"gear_completion_percent": 20, "role": "unknown", "review_status": "stale"})
    first = system.memory.append({"type": "episodic", "action": "reject", "outcome": "blocked"})
    second = system.memory.append({"type": "graph", "fact": "account owns item"})
    patterns = system.memory.update_patterns()

    assert blocked["decision"] == "REJECT"
    assert "api_key_leak" in blocked["reason"]
    assert economy["items"][0]["liquidity"] == "illiquid"
    assert economy["items"][0]["price_forecast"] >= 0
    assert meta["raid_viability"] == "not_ready"
    assert [event["id"] for event in system.memory.search("blocked")] == [first["id"]]
    assert patterns["patterns"] == {"episodic": 1, "graph": 1}
    assert second["id"] != first["id"]


def test_persistence_adapters_export_and_store_snapshot():
    state_path = Path("data/test_expert_ai_state.json")
    if state_path.exists():
        state_path.unlink()
    config = ExpertAIServiceConfig(
        postgres_url="",
        neo4j_url="bolt://neo4j:7687",
        qdrant_url="",
        redis_url="",
        state_path=str(state_path),
    )
    system = ExpertAISystem()
    system.persistence = ExpertAIPersistence(config)
    system.runtime.add_entity({"id": "account:persist", "type": "account_snapshot"})
    system.runtime.add_entity({"id": "item:persist", "type": "Item"})
    system.runtime.add_relation({"source": "account:persist", "target": "item:persist", "relation_type": "owns"})

    snapshot = system.runtime.snapshot()
    stored = system.persistence.persist_snapshot(snapshot)
    loaded = system.persistence.local_state.load_runtime_snapshot(snapshot.id)
    graph_export = system.persistence.export_graph(system.runtime.graph.to_dict())
    event_store = system.persistence.persist_memory(system.memory.append({"type": "vector", "fact": "persisted memory"}))
    readiness = system.persistence.readiness()

    assert stored["stored"] is True
    assert stored["postgres"]["written"] is False
    assert loaded is not None
    assert "account:persist" in loaded.entities
    assert graph_export["configured"] is True
    assert graph_export["statement_count"] == 3
    assert len(event_store["qdrant"]["point"]["vector"]) == 16
    assert event_store["qdrant"]["written"] is False
    assert system.persistence.health()["config"]["postgres_url"] == ""
    assert readiness["services"]["postgres"]["ready"] is False
    assert readiness["services"]["neo4j"]["ready"] is False
    assert readiness["ready"] is False
    if state_path.exists():
        state_path.unlink()


def test_production_client_adapters_execute_write_read_paths():
    class FakeNeo4jResult:
        def __init__(self, row=None):
            self.row = row or {"id": "account:neo4j", "type": "account_snapshot", "properties": {"name": "Neo4j"}}

        def single(self):
            return self.row

    class FakeNeo4jPing:
        def single(self):
            return {"ok": 1}

    class FakeNeo4jSession:
        def __init__(self):
            self.runs = []

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def run(self, statement, **parameters):
            self.runs.append((statement, parameters))
            if statement == "RETURN 1 AS ok":
                return FakeNeo4jPing()
            return FakeNeo4jResult()

    class FakeNeo4jDriver:
        def __init__(self):
            self.session_obj = FakeNeo4jSession()
            self.closed = False

        def session(self):
            return self.session_obj

        def close(self):
            self.closed = True

    fake_driver = FakeNeo4jDriver()
    neo4j = Neo4jGraphAdapter("bolt://neo4j:7687", "neo4j", "secret", driver_factory=lambda *_args, **_kwargs: fake_driver)
    written = neo4j.write_graph({"nodes": [{"id": "account:neo4j", "type": "account_snapshot", "properties": {}}], "edges": []})
    node = neo4j.read_node("account:neo4j")

    assert written["written"] is True
    assert written["statement_count"] == 1
    assert node["id"] == "account:neo4j"
    assert neo4j.readiness()["ready"] is True
    assert fake_driver.closed is True

    class FakePgConnection:
        def __init__(self):
            self.queries = []

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def execute(self, query, params=None):
            self.queries.append((query, params))
            return self

        def fetchone(self):
            if self.queries[-1][0] == "SELECT 1":
                return (1,)
            return ("snapshot:1", 1.0, {"entities": {}, "relations": []})

        def commit(self):
            self.queries.append(("COMMIT", None))

    fake_pg = FakePgConnection()
    postgres = PostgresStateAdapter("postgresql://gw2:secret@postgres/db", connection_factory=lambda _url: fake_pg)
    system = ExpertAISystem()
    snapshot = system.runtime.snapshot()

    assert postgres.migrate()["migrated"] is True
    assert postgres.write_snapshot(snapshot)["written"] is True
    assert postgres.read_snapshot("snapshot:1")["id"] == "snapshot:1"
    assert postgres.readiness()["ready"] is True
    assert any("CREATE TABLE" in query for query, _params in fake_pg.queries)
    assert any("expert_ai_schema_migrations" in query for query, _params in fake_pg.queries)

    class FakeRedis:
        def xadd(self, queue, fields):
            self.queue = queue
            self.fields = fields
            return b"1-0"

        def xread(self, *_args, **_kwargs):
            return [(b"expert_ai_tasks", [(b"1-0", {b"payload": self.fields["payload"].encode("utf-8")})])]

        def xdel(self, queue, task_id):
            self.deleted = (queue, task_id)
            return 1

        def ping(self):
            return True

    fake_redis = FakeRedis()
    redis = RedisQueueAdapter("redis://redis:6379/0", client_factory=lambda _url: fake_redis)

    assert redis.enqueue({"type": "health"})["task_id"] == "1-0"
    assert redis.dequeue()[0]["payload"]["type"] == "health"
    assert redis.ack("1-0")["acked"] is True
    assert redis.readiness()["ready"] is True


def test_expert_layer_is_read_only_and_generates_counterfactuals():
    system = ExpertAISystem()
    before_state = system.runtime.state()
    decision = system.evaluate_decision({
        "factors": [
            {"name": "confidence", "value": 0.9, "weight": 1, "impact": "positive"},
            {"name": "cost_risk", "value": 0.2, "weight": 1, "impact": "negative"},
        ],
    })

    explanation = system.expert_layer.explain_decision(decision, context={"goal": "legendary"})
    counterfactuals = system.expert_layer.generate_counterfactuals(decision)
    thinking = system.expert_layer.simulate_expert_thinking("What should I do next?", graph=system.runtime.graph.to_dict())

    assert explanation["mode"] == "read_only"
    assert explanation["explanation"]["key_factors"]
    assert counterfactuals["mutates_state"] is False
    assert thinking["mutates_state"] is False
    assert system.runtime.state()["nodes"] == before_state["nodes"]


def test_memory_feedback_loop_updates_patterns_and_weights():
    system = ExpertAISystem()

    success = system.feedback.observe({"decision": "APPROVE", "outcome": "success", "risk": 0})
    failure = system.feedback.observe({"decision": "REVIEW", "outcome": "failed", "risk": 0.4})

    assert success["evaluation"]["success"] is True
    assert success["reasoning_weights"]["approve_success"] > 1
    assert failure["evaluation"]["success"] is False
    assert failure["reasoning_weights"]["risk_penalty"] > 1
    assert system.feedback.status()["event_count"] == 2


def test_expert_ai_routes_smoke():
    client = TestClient(app)

    graph = client.post("/graph/compile", json={"file_path": "domain_graph.yaml"})
    assert graph.status_code == 200
    graph_id = graph.json()["id"]
    assert client.get(f"/graph/{graph_id}").status_code == 200

    snapshot = client.post("/runtime/snapshot", json={
        "entities": [{"id": "account:test", "type": "account_snapshot"}],
        "relations": [],
    })
    assert snapshot.status_code == 200

    decision = client.post("/decision/evaluate", json={
        "factors": [{"name": "quality", "value": 0.8, "weight": 1, "impact": "positive"}],
    })
    assert decision.status_code == 200
    assert decision.json()["decision"] == "APPROVE"

    memory = client.post("/memory/append", json={"type": "graph", "fact": "account owns item"})
    assert memory.status_code == 200
    search = client.get("/memory/search", params={"query": "owns"})
    assert search.status_code == 200
    assert search.json()["results"]

    node = client.post("/graph/node", json={"id": "item:test", "type": "Item", "properties": {"name": "Test Item"}})
    assert node.status_code == 200
    found = client.get("/runtime/search", params={"query": "Test Item"})
    assert found.status_code == 200
    assert found.json()["results"]

    edge = client.post("/graph/edge", json={"source": "account:test", "target": "item:test", "relation_type": "owns"})
    assert edge.status_code == 200
    neighbors = client.get("/runtime/neighbors/account:test")
    assert any(n["id"] == "item:test" for n in neighbors.json()["results"])
    trace = client.get("/runtime/trace/account:test")
    assert trace.status_code == 200

    health = client.get("/persistence/health")
    assert health.status_code == 200
    assert "services" in health.json()

    readiness = client.get("/persistence/readiness")
    assert readiness.status_code == 200
    assert "services" in readiness.json()

    graph_export = client.post("/persistence/graph/export")
    assert graph_export.status_code == 200
    assert graph_export.json()["backend"] == "neo4j"

    migration = client.post("/persistence/migrate")
    assert migration.status_code == 200
    assert migration.json()["postgres"]["migrated"] is False

    feedback = client.post("/memory/feedback", json={"decision": "APPROVE", "outcome": "success"})
    assert feedback.status_code == 200
    assert feedback.json()["evaluation"]["success"] is True

    explain = client.post("/expert/explain", json={"decision": decision.json(), "context": {"goal": "legendary"}})
    assert explain.status_code == 200
    assert explain.json()["mode"] == "read_only"

    think = client.post("/expert/think", json={"prompt": "Plan next step"})
    assert think.status_code == 200
    assert think.json()["mutates_state"] is False

    queue = client.post("/queue/enqueue", json={"type": "health"})
    assert queue.status_code == 200
    assert queue.json()["queued"] is False


def test_expert_ai_routes_error_boundaries():
    client = TestClient(app)

    missing_graph = client.get("/graph/not-found")
    missing_entity = client.get("/runtime/entity/not-found")
    rollback_without_id = client.post("/runtime/rollback", json={})
    trace_without_node = client.post("/reasoning/trace", json={})
    account_snapshot_without_key = client.post("/training/account_snapshot", json={})
    unsupported_action = client.post("/runtime/action", json={"type": "unsupported"})
    explain_without_decision = client.post("/expert/explain", json={})

    assert missing_graph.status_code == 404
    assert missing_entity.status_code == 404
    assert rollback_without_id.status_code == 422
    assert trace_without_node.status_code == 422
    assert account_snapshot_without_key.status_code == 422
    assert unsupported_action.status_code == 200
    assert unsupported_action.json()["status"] == "failed"
    assert explain_without_decision.status_code == 422


def test_worker_run_once_reports_ready_state():
    result = run_once()

    assert result["status"] == "ready"
    assert "persistence" in result
    assert "feedback" in result


def test_worker_consume_once_processes_queue_payload():
    class Persistence:
        def __init__(self):
            self.acked = []

        def dequeue_tasks(self, count=1):
            assert count == 1
            return [{"id": "task:1", "payload": {"type": "feedback", "payload": {"decision": "APPROVE", "outcome": "success"}}}]

        def ack_task(self, task_id):
            self.acked.append(task_id)
            return {"acked": True, "task_id": task_id}

    class System:
        def __init__(self):
            self.persistence = Persistence()

    system = System()
    result = consume_once(system)

    assert result["consumed"] == 1
    assert result["results"][0]["result"]["evaluation"]["success"] is True
    assert result["results"][0]["ack"]["acked"] is True
    assert system.persistence.acked == ["task:1"]
