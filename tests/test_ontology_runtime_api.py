"""Tests for the Ontology Runtime v1 API."""

from fastapi.testclient import TestClient

from gw2_progression.api.main import app


def test_ontology_runtime_api_ingest_trace_replay_and_llm_guard():
    client = TestClient(app)

    reset = client.post("/ontology/runtime/reset")
    assert reset.status_code == 200

    ingest = client.post(
        "/ontology/runtime/ingest",
        json={
            "raw": {
                "account": {"name": "Api.1234"},
                "snapshot_id": "snap-api",
                "assets": [{"item_id": 19721, "count": 2, "category": "material_storage", "total_value": 8}],
            }
        },
    )
    assert ingest.status_code == 200
    assert ingest.json()["entity_count"] == 2
    assert ingest.json()["relation_count"] == 1

    executed = client.post(
        "/ontology/runtime/execute",
        json={
            "actions": [
                {
                    "node_id": "update",
                    "type": "update_entity",
                    "entity_id": "asset:Api.1234:material_storage:19721:0",
                    "patch": {"count": 3},
                }
            ]
        },
    )
    assert executed.status_code == 200
    assert executed.json()["executed"] == 1

    simulated = client.post(
        "/ontology/runtime/simulate",
        json={
            "ticks": 1,
            "steps": [
                {
                    "type": "update_entity",
                    "entity_id": "asset:Api.1234:material_storage:19721:0",
                    "patch": {"count": 4},
                }
            ],
        },
    )
    assert simulated.status_code == 200
    assert simulated.json()["time"] == 1

    reasoning = client.post(
        "/ontology/runtime/reasoning/action",
        json={
            "type": "update_entity",
            "entity_id": "asset:Api.1234:material_storage:19721:0",
            "patch": {"count": 5},
        },
    )
    assert reasoning.status_code == 200
    assert reasoning.json()["status"] == "accepted"

    lineage = client.get("/ontology/runtime/lineage")
    assert lineage.status_code == 200
    assert len(lineage.json()["lineage"]) >= 4

    trace = client.get("/ontology/runtime/trace/account:Api.1234")
    assert trace.status_code == 200
    assert len(trace.json()["steps"]) == 1

    rejected = client.post(
        "/ontology/runtime/llm/action",
        json={
            "type": "add_relation",
            "relation": {"source": "missing", "target": "also-missing", "relation_type": "owns"},
        },
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"

    replay = client.post("/ontology/runtime/replay")
    assert replay.status_code == 200
    assert replay.json()["deterministic"] is True


def test_ontology_runtime_v2_foundry_compile_decision_rl_and_guarantees_api():
    client = TestClient(app)

    reset = client.post("/ontology/runtime/reset")
    assert reset.status_code == 200

    actions = [
        {
            "node_id": "asset",
            "type": "add_entity",
            "entity": {
                "id": "asset:api-foundry",
                "type": "account_asset",
                "properties": {"item_id": 19721, "count": 3, "location": "bank", "value": 5000},
            },
        }
    ]
    compiled = client.post("/ontology/runtime/compile", json={"graph_id": "api-foundry", "actions": actions})
    assert compiled.status_code == 200
    assert compiled.json()["manifest"]["kernel_version"] == "v3-execution-layer"
    assert compiled.json()["manifest"]["guarantees"]["dag_compilation"] is True
    assert compiled.json()["manifest"]["guarantees"]["dag_scheduling"] is True

    executed = client.post("/ontology/runtime/compiled/execute", json={"graph_id": "api-foundry", "actions": actions})
    assert executed.status_code == 200
    assert executed.json()["executed"] == 1
    assert executed.json()["scheduler"]["strategy"] == "deterministic-ready-queue"
    assert executed.json()["manifest"]["guarantees"]["ontology_enforcement"] is True

    decision = client.post("/ontology/runtime/decision/decide", json={"objective": "LIQUIDITY"})
    assert decision.status_code == 200
    assert decision.json()["decision"]["source"] == "BORS"
    assert decision.json()["execution"]["executed"] == 1

    optimized = client.post("/ontology/runtime/rl/optimize", json={"rewards": {"sell": 2.0, "hold": 1.0}})
    assert optimized.status_code == 200
    assert optimized.json()["execution"]["executed"] == 2

    guarantees = client.get("/ontology/runtime/guarantees")
    assert guarantees.status_code == 200
    assert guarantees.json()["everything_is_execution_graph"] is True
    assert guarantees.json()["deterministic_execution"] is True
    assert guarantees.json()["lineage_replay"] is True


def test_ontology_runtime_v3_scheduler_execute_api_returns_tick_trace():
    client = TestClient(app)
    tenant = {"X-Ontology-Tenant": "v3-api"}

    assert client.post("/ontology/runtime/reset", headers=tenant).status_code == 200
    response = client.post(
        "/ontology/runtime/scheduler/execute",
        headers=tenant,
        json={
            "graph_id": "api-scheduler",
            "actions": [
                {
                    "node_id": "asset:a",
                    "type": "add_entity",
                    "entity": {
                        "id": "asset:v3:a",
                        "type": "account_asset",
                        "properties": {"item_id": 1, "count": 1, "location": "bank"},
                    },
                },
                {
                    "node_id": "asset:b",
                    "depends_on": [],
                    "type": "add_entity",
                    "entity": {
                        "id": "asset:v3:b",
                        "type": "account_asset",
                        "properties": {"item_id": 2, "count": 1, "location": "bank"},
                    },
                },
                {
                    "node_id": "update:b",
                    "depends_on": ["asset:b"],
                    "type": "update_entity",
                    "entity_id": "asset:v3:b",
                    "patch": {"count": 2},
                },
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["graph"]["manifest"]["kernel_version"] == "v3-execution-layer"
    assert body["scheduler"]["complete"] is True
    assert body["execution"]["ticks"][0]["ready_nodes"] == ["asset:a", "asset:b"]
    assert body["execution"]["ticks"][1]["ready_nodes"] == ["update:b"]


def test_ontology_runtime_vfinal_convergence_and_kernel_action_api():
    client = TestClient(app)
    tenant = {"X-Ontology-Tenant": "vfinal-api"}

    assert client.post("/ontology/runtime/reset", headers=tenant).status_code == 200
    convergence = client.get("/ontology/runtime/convergence", headers=tenant)
    assert convergence.status_code == 200
    assert convergence.json()["kernel"] == "OntologyKernel"
    assert convergence.json()["rules"]["single_execution_kernel"] is True

    executed = client.post(
        "/ontology/runtime/kernel/action",
        headers=tenant,
        json={
            "source": "api-test",
            "action": {
                "type": "add_entity",
                "entity": {
                    "id": "asset:vfinal",
                    "type": "account_asset",
                    "properties": {"item_id": 19721, "count": 1, "location": "bank"},
                },
            },
        },
    )
    assert executed.status_code == 200
    assert executed.json()["kernel"] == "OntologyKernel"
    assert executed.json()["execution"]["scheduler"]["complete"] is True
