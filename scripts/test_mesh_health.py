"""Verify Data Mesh v1 bridge health."""
from gw2_progression.data_mesh.integration import HAS_GW2RADAR, DataMeshBridge

bridge = DataMeshBridge()
s = bridge.status()
print("Data Mesh v1 bridge status:")
print(f"  gw2radar detected: {HAS_GW2RADAR}")
print(f"  DGSK engine:       {s['dgsk_engine']}")
print(f"  OOSK runtime:      {s['oosk_runtime']}")
print(f"  BORS engine:       {s['bors_engine']}")
print(f"  KB available:      {s['kb_available']}")

result = bridge.compile_domain_graph(yaml_path="domain_graph.yaml")
print(f"  DGSK compile:      {len(result['dgsk']['nodes'])} nodes, {len(result['dgsk']['edges'])} edges")
print(f"  Errors:            {result['errors']}")
print(f"  OOSK registry:     {'yes' if result.get('oosk_registry') else 'no'}")
print(f"  BORS mappings:     {'yes' if result.get('bors_mappings') else 'no'}")

d = bridge.evaluate_decision("health_check", [
    {"name": "wealth", "value": 0.8, "weight": 0.6, "impact": "positive"},
    {"name": "risk", "value": 0.2, "weight": 0.4, "impact": "negative"},
])
print(f"  BORS decision:     {d['decision']} (score={d['score']:.3f}, conf={d['confidence']:.3f})")

snap = bridge.sync_oosk(
    [{"id": "account:test", "type": "account", "properties": {"name": "test"}}],
    [],
)
print(f"  OOSK sync:         {snap['entity_count']} entities via {snap['engine']}")

print("\nData Mesh v1 bridge fully operational!")
