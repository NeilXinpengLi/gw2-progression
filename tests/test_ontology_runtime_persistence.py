from fastapi.testclient import TestClient

from gw2_progression import database
from gw2_progression.api.main import app
from gw2_progression.ontology import OntologyKernel


def test_ontology_kernel_persists_state_and_replays_lineage(tmp_path, monkeypatch):
    db_path = tmp_path / "ontology-runtime.db"
    monkeypatch.setattr(database, "_TEST_DB_URL", str(db_path))

    kernel = OntologyKernel(tenant_id="persist-direct")
    executed = kernel.execute(
        {
            "type": "add_entity",
            "entity": {
                "id": "asset:persisted",
                "type": "account_asset",
                "properties": {"item_id": 19721, "count": 2, "location": "bank"},
            },
        }
    )

    assert executed["persistence"]["persisted"] is True
    assert executed["persistence"]["lineage_count"] == 1

    restored = OntologyKernel(tenant_id="persist-direct", load_persisted=True)
    snapshot = restored.snapshot()

    assert "asset:persisted" in snapshot["state"]["entities"]
    assert snapshot["persistence"]["lineage_count"] == 1

    replay = restored.replay_persisted()
    assert replay["deterministic"] is True
    assert replay["persisted_state_hash"] == replay["replayed_state_hash"]


def test_ontology_runtime_persistence_api_reports_and_replays(tmp_path, monkeypatch):
    db_path = tmp_path / "ontology-runtime-api.db"
    monkeypatch.setattr(database, "_TEST_DB_URL", str(db_path))

    client = TestClient(app)
    tenant = {"X-Ontology-Tenant": "persist-api"}

    reset = client.post("/ontology/runtime/reset", headers=tenant)
    assert reset.status_code == 200

    executed = client.post(
        "/ontology/runtime/kernel/action",
        headers=tenant,
        json={
            "source": "persistence-test",
            "action": {
                "type": "add_entity",
                "entity": {
                    "id": "asset:persist-api",
                    "type": "account_asset",
                    "properties": {"item_id": 1, "count": 1, "location": "inventory"},
                },
            },
        },
    )
    assert executed.status_code == 200
    assert executed.json()["execution"]["results"][0]["result"]["persistence"]["persisted"] is True

    status = client.get("/ontology/runtime/persistence", headers=tenant)
    assert status.status_code == 200
    assert status.json()["persistence"]["enabled"] is True
    assert status.json()["persistence"]["lineage_count"] == 1

    replay = client.post("/ontology/runtime/persistence/replay", headers=tenant)
    assert replay.status_code == 200
    assert replay.json()["deterministic"] is True
    assert replay.json()["lineage_count"] == 1
