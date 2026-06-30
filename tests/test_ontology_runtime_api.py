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
