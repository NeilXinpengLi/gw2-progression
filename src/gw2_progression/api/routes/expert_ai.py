"""GW2 Expert AI training infrastructure endpoints."""

from fastapi import APIRouter, Body, HTTPException

from gw2_progression.expert_ai.adapters import account_contents_to_runtime_payload
from gw2_progression.expert_ai.core import edge_to_dict, expert_ai, node_to_dict
from gw2_progression.expert_ai.training import build_dataset
from gw2_progression.gw2_client import Gw2ApiError
from gw2_progression.services.auth_service import get_api_key

router = APIRouter(tags=["expert-ai"])


@router.post("/graph/compile")
async def compile_graph(body: dict = Body(default_factory=dict)):
    return expert_ai.compile_graph(payload=body.get("domain_graph"), file_path=body.get("file_path"))


@router.get("/graph/{graph_id}")
async def get_graph(graph_id: str):
    graph = expert_ai.compiled_graphs.get(graph_id)
    if not graph:
        raise HTTPException(status_code=404, detail="graph not found")
    return graph


@router.post("/runtime/snapshot")
async def runtime_snapshot(body: dict = Body(default_factory=dict)):
    for entity in body.get("entities", []):
        expert_ai.runtime.add_entity(entity)
    for relation in body.get("relations", []):
        expert_ai.runtime.add_relation(relation)
    snapshot = expert_ai.runtime.snapshot()
    return {
        "snapshot_id": snapshot.id,
        "created_at": snapshot.created_at,
        "entity_count": len(snapshot.entities),
        "relation_count": len(snapshot.relations),
    }


@router.get("/runtime/state")
async def runtime_state():
    return expert_ai.runtime.state()


@router.get("/runtime/entity/{entity_id}")
async def runtime_entity(entity_id: str):
    node = expert_ai.runtime.get_entity(entity_id)
    if not node:
        raise HTTPException(status_code=404, detail="entity not found")
    return node_to_dict(node)


@router.get("/runtime/search")
async def runtime_search(query: str = "", node_type: str | None = None, limit: int = 20):
    return {"results": [node_to_dict(n) for n in expert_ai.runtime.graph.search(query=query, node_type=node_type, limit=limit)]}


@router.get("/runtime/neighbors/{node_id}")
async def runtime_neighbors(node_id: str, relation_type: str | None = None):
    return {"results": [node_to_dict(n) for n in expert_ai.runtime.graph.neighbors(node_id, relation_type=relation_type)]}


@router.get("/runtime/trace/{node_id}")
async def runtime_trace(node_id: str, depth: int = 3):
    return expert_ai.runtime.graph.traverse(node_id, depth=depth)


@router.post("/runtime/action")
async def runtime_action(body: dict = Body(...)):
    return expert_ai.runtime.execute(body)


@router.post("/runtime/rollback")
async def runtime_rollback(body: dict = Body(...)):
    snapshot_id = body.get("snapshot_id")
    if not snapshot_id:
        raise HTTPException(status_code=422, detail="snapshot_id required")
    return {"rolled_back": expert_ai.runtime.rollback(snapshot_id)}


@router.post("/reasoning/analyze")
async def reasoning_analyze(body: dict = Body(default_factory=dict)):
    return expert_ai.reasoning.analyze(start=body.get("start"), goal=body.get("goal"), depth=int(body.get("depth", 2)))


@router.post("/reasoning/trace")
async def reasoning_trace(body: dict = Body(...)):
    node_id = body.get("node_id")
    if not node_id:
        raise HTTPException(status_code=422, detail="node_id required")
    return expert_ai.reasoning.trace(node_id, depth=int(body.get("depth", 3)))


@router.post("/economy/simulate")
async def economy_simulate(body: dict = Body(default_factory=dict)):
    return expert_ai.economy.simulate(body.get("items", []))


@router.post("/meta/analyze_build")
async def meta_analyze_build(body: dict = Body(...)):
    return expert_ai.meta.analyze_build(body)


@router.post("/plan/generate")
async def plan_generate(body: dict = Body(default_factory=dict)):
    return expert_ai.planner.generate(body.get("goals", []), constraints=body.get("constraints", {}))


@router.post("/decision/evaluate")
async def decision_evaluate(body: dict = Body(...)):
    return expert_ai.evaluate_decision(body)


@router.post("/memory/append")
async def memory_append(body: dict = Body(...)):
    return expert_ai.memory.append(body)


@router.get("/memory/search")
async def memory_search(query: str = "", memory_type: str | None = None, limit: int = 20):
    return {"results": expert_ai.memory.search(query=query, memory_type=memory_type, limit=limit)}


@router.post("/memory/update_patterns")
async def memory_update_patterns():
    return expert_ai.memory.update_patterns()


@router.post("/memory/feedback")
async def memory_feedback(body: dict = Body(...)):
    return expert_ai.feedback.observe(body)


@router.get("/memory/feedback/status")
async def memory_feedback_status():
    return expert_ai.feedback.status()


@router.get("/persistence/health")
async def persistence_health():
    return expert_ai.persistence.health()


@router.get("/persistence/readiness")
async def persistence_readiness():
    return expert_ai.persistence.readiness()


@router.post("/persistence/snapshot")
async def persistence_snapshot():
    snapshot = expert_ai.runtime.snapshot()
    return expert_ai.persistence.persist_snapshot(snapshot)


@router.post("/persistence/migrate")
async def persistence_migrate():
    return expert_ai.persistence.migrate()


@router.post("/persistence/graph/export")
async def persistence_graph_export():
    return expert_ai.persistence.export_graph(expert_ai.runtime.graph.to_dict())


@router.post("/persistence/graph/write")
async def persistence_graph_write():
    return expert_ai.persistence.write_graph(expert_ai.runtime.graph.to_dict())


@router.post("/queue/enqueue")
async def queue_enqueue(body: dict = Body(...)):
    return expert_ai.persistence.enqueue_task(body)


@router.post("/queue/dequeue")
async def queue_dequeue(body: dict = Body(default_factory=dict)):
    return {"tasks": expert_ai.persistence.dequeue_tasks(count=int(body.get("count", 1)))}


@router.get("/memory/vector/search")
async def memory_vector_search(query: str, limit: int = 10):
    return expert_ai.persistence.qdrant.search(query, limit=limit)


@router.post("/expert/explain")
async def expert_explain(body: dict = Body(...)):
    decision = body.get("decision", {})
    if not decision:
        raise HTTPException(status_code=422, detail="decision required")
    return expert_ai.expert_layer.explain_decision(decision, context=body.get("context", {}))


@router.post("/expert/counterfactuals")
async def expert_counterfactuals(body: dict = Body(...)):
    decision = body.get("decision", {})
    if not decision:
        raise HTTPException(status_code=422, detail="decision required")
    return expert_ai.expert_layer.generate_counterfactuals(decision, limit=int(body.get("limit", 3)))


@router.post("/expert/think")
async def expert_think(body: dict = Body(default_factory=dict)):
    graph = body.get("graph", expert_ai.runtime.graph.to_dict())
    return expert_ai.expert_layer.simulate_expert_thinking(body.get("prompt", ""), graph=graph)


@router.post("/training/dataset")
async def training_dataset(body: dict = Body(default_factory=dict)):
    return build_dataset(body.get("snapshot", expert_ai.runtime.graph.to_dict()), dataset_type=body.get("dataset_type", "reasoning_graph"))


@router.post("/training/account_snapshot")
async def training_account_snapshot(body: dict = Body(...)):
    api_key = body.get("api_key", "")
    if not api_key:
        raise HTTPException(status_code=422, detail="api_key required")
    try:
        from gw2_progression.analyzer import fetch_all

        contents = await fetch_all(await get_api_key(api_key))
    except Gw2ApiError as e:
        raise HTTPException(status_code=401, detail=e.message)

    payload = account_contents_to_runtime_payload(contents, item_limit=int(body.get("item_limit", 200)))
    for entity in payload["entities"]:
        expert_ai.runtime.add_entity(entity)
    for relation in payload["relations"]:
        expert_ai.runtime.add_relation(relation)
    snapshot = expert_ai.runtime.snapshot()
    dataset = build_dataset({"graph": expert_ai.runtime.graph.to_dict()}, dataset_type=body.get("dataset_type", "account_snapshot"))
    return {"snapshot_id": snapshot.id, "summary": payload["summary"], "dataset": dataset}


@router.post("/graph/node")
async def graph_node(body: dict = Body(...)):
    return node_to_dict(expert_ai.runtime.add_entity(body))


@router.post("/graph/edge")
async def graph_edge(body: dict = Body(...)):
    return edge_to_dict(expert_ai.runtime.add_relation(body))
