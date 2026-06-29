"""Tests for GW2 Data Mesh v1 integration bridge."""

from __future__ import annotations

from gw2_progression.data_mesh.integration import DataMeshBridge, check_mesh_health


def test_mesh_health_check():
    """Mesh health check returns expected structure."""
    health = check_mesh_health()
    assert health["mesh_version"] == "v1"
    assert health["dgsk_engine"] in ("gw2radar", "local")


def test_mesh_bridge_status():
    """DataMeshBridge.status() returns all layer info."""
    bridge = DataMeshBridge()
    s = bridge.status()
    assert s["mesh_version"] == "v1"
    assert "dgsk_engine" in s
    assert "oosk_runtime" in s
    assert "bors_engine" in s


def test_schema_normalization_simple():
    """normalize() handles minimal input."""
    result = DataMeshBridge.normalize({"account": "Test.1234", "wallet": [{"gold": 100}]})
    assert result["account"] == "Test.1234"
    assert len(result["wallet"]) == 1


def test_schema_normalization_fallback():
    """normalize() falls back gracefully for missing fields."""
    result = DataMeshBridge.normalize({})
    assert result["account"] == "unknown"
    assert result["items"] == []


def test_multi_source_ingest_empty():
    """multi_source_ingest with empty list returns nothing."""
    bridge = DataMeshBridge()
    results = bridge.multi_source_ingest([])
    assert results == []


def test_multi_source_ingest_unsupported():
    """Unknown source types return 'unsupported' status."""
    bridge = DataMeshBridge()
    results = bridge.multi_source_ingest([{"type": "reddit", "params": {}}])
    assert results[0]["status"] == "unsupported"


def test_dgsk_compilation():
    """Compile domain_graph.yaml through DGSK engine."""
    bridge = DataMeshBridge()
    import os
    import tempfile
    yaml_content = """
domain: test
version: "1.0"
nodes:
  - type: test_item
    description: Test
    properties:
      - name: "id (int, required)"
edges: []
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as f:
        f.write(yaml_content)
        tmp_path = f.name
    try:
        result = bridge.compile_domain_graph(yaml_path=tmp_path)
        assert "errors" in result
        assert "dgsk" in result
    finally:
        os.unlink(tmp_path)


def test_bors_decision():
    """BORS decision evaluation returns structured result."""
    bridge = DataMeshBridge()
    result = bridge.evaluate_decision("test_decision", [
        {"name": "factor_a", "value": 0.8, "weight": 0.7, "impact": "positive"},
        {"name": "factor_b", "value": 0.2, "weight": 0.3, "impact": "negative"},
    ])
    assert "decision" in result
    assert "score" in result
    assert "confidence" in result


def test_oosk_sync_empty():
    """OOSK sync with empty data creates a snapshot."""
    bridge = DataMeshBridge()
    result = bridge.sync_oosk([], [])
    assert "snapshot_id" in result
    assert result["entity_count"] == 0
    assert result["relation_count"] == 0


def test_oosk_sync_with_entities():
    """OOSK sync with entities creates a populated snapshot."""
    bridge = DataMeshBridge()
    entities = [{"id": "test:1", "type": "TestEntity", "properties": {"name": "test"}}]
    relations = [{"source": "test:1", "relation_type": "related_to", "target": "test:2"}]
    result = bridge.sync_oosk(entities, relations)
    assert result["entity_count"] >= 1  # may be >1 if graph auto-creates implicit entities


def test_training_rounds():
    """Training pipeline produces model artifacts."""
    bridge = DataMeshBridge()
    dataset = {
        "version": "test-v1",
        "examples": [{
            "id": "ex-1",
            "state": {"graph": {"nodes": [{"id": "n1"}], "edges": []}},
            "reasoning_chain": [{"from": "n1", "relation": "test", "to": "n2"}],
            "decision": {"type": "training_label", "status": "test"},
            "label": {"quality": "test_labeled"},
        }],
    }
    models = bridge.run_training(dataset, model_type="test_model", rounds=2)
    assert len(models) == 2
    for m in models:
        assert m["status"] in ("trained", "empty")
        assert "model_id" in m


def test_dgsk_compilation_real_yaml():
    """Compile the actual domain_graph.yaml from the project root."""
    from pathlib import Path
    bridge = DataMeshBridge()
    yaml_path = str(Path.cwd() / "domain_graph.yaml")
    if Path(yaml_path).exists():
        result = bridge.compile_domain_graph(yaml_path=yaml_path)
        assert result["dgsk"]["domain"] == "gw2-progression"
        assert len(result["dgsk"]["nodes"]) >= 10
    else:
        import pytest
        pytest.skip("domain_graph.yaml not found")


def test_ingest_gw2api_no_key():
    """Ingesting without an API key returns error."""
    bridge = DataMeshBridge()
    result = bridge.multi_source_ingest([{"type": "gw2_api", "params": {}}])
    assert result[0]["status"] == "error"
    assert result[0].get("error") in ("GW2 API key required", "no api_key")
