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


def test_ontology_kernel_persists_compiled_manifest(tmp_path, monkeypatch):
    db_path = tmp_path / "ontology-runtime-manifest.db"
    monkeypatch.setattr(database, "_TEST_DB_URL", str(db_path))

    kernel = OntologyKernel(tenant_id="persist-manifest")
    compiled = kernel.compile(
        [
            {
                "node_id": "asset",
                "type": "add_entity",
                "entity": {
                    "id": "asset:manifest",
                    "type": "account_asset",
                    "properties": {"item_id": 19721, "count": 1, "location": "bank"},
                },
            }
        ],
        graph_id="manifest-test",
    )

    manifest = compiled.to_dict()
    loaded = kernel.persistence.load_manifest(compiled.graph_id)
    listed = kernel.persistence.list_manifests()

    assert manifest["persistence"]["persisted"] is True
    assert manifest["manifest"]["manifest_hash"] == manifest["persistence"]["manifest_hash"]
    assert manifest["persistence"]["signature_status"] == "valid"
    assert loaded is not None
    assert loaded["manifest"]["manifest_hash"] == manifest["manifest"]["manifest_hash"]
    assert loaded["signature_status"] == "valid"
    assert loaded["manifest_signature"] == manifest["persistence"]["manifest_signature"]
    assert listed[0]["graph_id"] == compiled.graph_id
    assert listed[0]["signature_status"] == "valid"
    assert kernel.persistence.status()["manifest_count"] == 1
    assert kernel.persistence.status()["signed_manifest_count"] == 1
    assert kernel.guarantees()["persistent_manifests"] is True
    assert kernel.guarantees()["signed_manifests"] is True


def test_ontology_kernel_detects_manifest_signature_tampering(tmp_path, monkeypatch):
    db_path = tmp_path / "ontology-runtime-manifest-tamper.db"
    monkeypatch.setattr(database, "_TEST_DB_URL", str(db_path))

    kernel = OntologyKernel(tenant_id="manifest-tamper")
    compiled = kernel.compile(
        [
            {
                "node_id": "asset",
                "type": "add_entity",
                "entity": {
                    "id": "asset:tamper",
                    "type": "account_asset",
                    "properties": {"item_id": 19721, "count": 1, "location": "bank"},
                },
            }
        ],
        graph_id="manifest-tamper",
    )

    with kernel.persistence._connect() as conn:
        conn.execute(
            """
            UPDATE ontology_kernel_manifests
            SET manifest_signature = ?
            WHERE tenant_id = ? AND graph_id = ?
            """,
            ("tampered", kernel.tenant_id, compiled.graph_id),
        )
        conn.commit()

    loaded = kernel.persistence.load_manifest(compiled.graph_id)
    listed = kernel.persistence.list_manifests()

    assert loaded is not None
    assert loaded["signature_status"] == "invalid"
    assert listed[0]["signature_status"] == "invalid"
    assert kernel.persistence.status()["signed_manifest_count"] == 0
    assert kernel.guarantees()["signed_manifests"] is False


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
    assert status.json()["persistence"]["manifest_count"] >= 1

    replay = client.post("/ontology/runtime/persistence/replay", headers=tenant)
    assert replay.status_code == 200
    assert replay.json()["deterministic"] is True
    assert replay.json()["lineage_count"] == 1
