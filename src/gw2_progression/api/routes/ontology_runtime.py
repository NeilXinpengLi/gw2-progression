"""Ontology Runtime v1 API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException

from gw2_progression.ontology import OntologyRuntimeKernel, OntologyViolation

router = APIRouter(prefix="/ontology/runtime", tags=["ontology-runtime"])

_kernel = OntologyRuntimeKernel()


@router.get("/state")
async def ontology_runtime_state():
    return _kernel.snapshot()


@router.post("/reset")
async def ontology_runtime_reset():
    global _kernel
    _kernel = OntologyRuntimeKernel()
    return {"status": "reset", "state_hash": _kernel.snapshot()["state_hash"]}


@router.post("/action")
async def ontology_runtime_action(body: dict = Body(...)):
    try:
        return _kernel.execute(body)
    except OntologyViolation as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/execute")
async def ontology_runtime_execute(body: dict = Body(default_factory=dict)):
    actions = body.get("actions", [])
    if not isinstance(actions, list) or not actions:
        raise HTTPException(status_code=422, detail="actions must be a non-empty list")
    try:
        return _kernel.execute_graph(actions)
    except OntologyViolation as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/simulate")
async def ontology_runtime_simulate(body: dict = Body(default_factory=dict)):
    steps = body.get("steps", [])
    if not isinstance(steps, list):
        raise HTTPException(status_code=422, detail="steps must be a list")
    try:
        return _kernel.simulate(steps, ticks=int(body.get("ticks", 1)))
    except OntologyViolation as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/llm/action")
async def ontology_runtime_llm_action(body: dict = Body(...)):
    return _kernel.execute_llm_action(body)


@router.post("/reasoning/action")
async def ontology_runtime_reasoning_action(body: dict = Body(...)):
    return _kernel.reasoning.execute(body)


@router.post("/ingest")
async def ontology_runtime_ingest(body: dict = Body(default_factory=dict)):
    try:
        if "raw" in body:
            return _kernel.ingest_raw_gw2(body["raw"])
        return _kernel.ingest_normalized(body)
    except OntologyViolation as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/trace/{entity_id}")
async def ontology_runtime_trace(entity_id: str, depth: int = 2):
    return _kernel.query().traverse(entity_id, depth=depth)


@router.get("/dependencies/{entity_id}")
async def ontology_runtime_dependencies(entity_id: str):
    return {"dependencies": _kernel.query().dependencies(entity_id)}


@router.get("/lineage")
async def ontology_runtime_lineage(limit: int = 50):
    return {"lineage": _kernel.lineage_store.list(limit=limit)}


@router.post("/replay")
async def ontology_runtime_replay(body: dict = Body(default_factory=dict)):
    lineage = body.get("lineage") or _kernel.snapshot()["lineage"]
    replay = _kernel.replay(lineage)
    return {
        "deterministic": replay["deterministic"],
        "mismatches": replay["mismatches"],
        "state": replay["state"].to_dict(),
        "lineage": replay["lineage"],
    }
