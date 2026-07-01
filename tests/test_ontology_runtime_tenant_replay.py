from fastapi.testclient import TestClient

from gw2_progression.api.main import app


def test_ontology_runtime_tenants_do_not_share_state():
    client = TestClient(app)
    tenant_a = {"X-Ontology-Tenant": "tenant-a"}
    tenant_b = {"X-Ontology-Tenant": "tenant-b"}

    assert client.post("/ontology/runtime/reset", headers=tenant_a).status_code == 200
    assert client.post("/ontology/runtime/reset", headers=tenant_b).status_code == 200

    created = client.post(
        "/ontology/runtime/action",
        headers=tenant_a,
        json={
            "type": "add_entity",
            "entity": {
                "id": "asset:tenant-a",
                "type": "account_asset",
                "properties": {"item_id": 19721, "count": 1, "location": "bank"},
            },
        },
    )
    assert created.status_code == 200

    state_a = client.get("/ontology/runtime/state", headers=tenant_a)
    state_b = client.get("/ontology/runtime/state", headers=tenant_b)

    assert "asset:tenant-a" in state_a.json()["state"]["entities"]
    assert "asset:tenant-a" not in state_b.json()["state"]["entities"]
    assert state_a.json()["compiled_guarantees"]["lineage_replay"] is True
    assert state_b.json()["compiled_guarantees"]["lineage_replay"] is True

