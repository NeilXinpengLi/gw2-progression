"""Ontology Runtime v2 Foundry API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Body, Header, HTTPException

from gw2_progression.ontology import OntologyRuntimeKernel, OntologyViolation

router = APIRouter(prefix="/ontology/runtime", tags=["ontology-runtime"])

_kernel = OntologyRuntimeKernel()
_kernels: dict[str, OntologyRuntimeKernel] = {"default": _kernel}


def _tenant_key(tenant_id: str) -> str:
    return tenant_id.strip() or "default"


def _kernel_for(tenant_id: str) -> OntologyRuntimeKernel:
    key = _tenant_key(tenant_id)
    if key not in _kernels:
        _kernels[key] = OntologyRuntimeKernel()
    return _kernels[key]


@router.get("/state")
async def ontology_runtime_state(tenant_id: str = Header("default", alias="X-Ontology-Tenant")):
    return _kernel_for(tenant_id).snapshot()


@router.get("/guarantees")
async def ontology_runtime_guarantees(tenant_id: str = Header("default", alias="X-Ontology-Tenant")):
    return _kernel_for(tenant_id).guarantees()


@router.post("/reset")
async def ontology_runtime_reset(tenant_id: str = Header("default", alias="X-Ontology-Tenant")):
    global _kernel
    key = _tenant_key(tenant_id)
    _kernels[key] = OntologyRuntimeKernel()
    if key == "default":
        _kernel = _kernels[key]
    return {"status": "reset", "tenant_id": key, "state_hash": _kernels[key].snapshot()["state_hash"]}


@router.post("/action")
async def ontology_runtime_action(body: dict = Body(...), tenant_id: str = Header("default", alias="X-Ontology-Tenant")):
    try:
        return _kernel_for(tenant_id).execute(body)
    except OntologyViolation as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/execute")
async def ontology_runtime_execute(body: dict = Body(default_factory=dict), tenant_id: str = Header("default", alias="X-Ontology-Tenant")):
    actions = body.get("actions", [])
    if not isinstance(actions, list) or not actions:
        raise HTTPException(status_code=422, detail="actions must be a non-empty list")
    try:
        return _kernel_for(tenant_id).execute_graph(actions)
    except OntologyViolation as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/compile")
async def ontology_runtime_compile(body: dict = Body(default_factory=dict), tenant_id: str = Header("default", alias="X-Ontology-Tenant")):
    actions = body.get("actions", [])
    if not isinstance(actions, list):
        raise HTTPException(status_code=422, detail="actions must be a list")
    try:
        return _kernel_for(tenant_id).compile(actions, graph_id=str(body.get("graph_id", "runtime"))).to_dict()
    except OntologyViolation as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/compiled/execute")
async def ontology_runtime_execute_compiled(body: dict = Body(default_factory=dict), tenant_id: str = Header("default", alias="X-Ontology-Tenant")):
    actions = body.get("actions", [])
    if not isinstance(actions, list) or not actions:
        raise HTTPException(status_code=422, detail="actions must be a non-empty list")
    try:
        kernel = _kernel_for(tenant_id)
        compiled = kernel.compile(actions, graph_id=str(body.get("graph_id", "runtime")))
        return kernel.execute_compiled(compiled)
    except OntologyViolation as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/scheduler/execute")
async def ontology_runtime_scheduler_execute(body: dict = Body(default_factory=dict), tenant_id: str = Header("default", alias="X-Ontology-Tenant")):
    actions = body.get("actions", [])
    if not isinstance(actions, list) or not actions:
        raise HTTPException(status_code=422, detail="actions must be a non-empty list")
    try:
        kernel = _kernel_for(tenant_id)
        compiled = kernel.compile(actions, graph_id=str(body.get("graph_id", "scheduler")))
        execution = kernel.execute_compiled(compiled)
        return {
            "graph": compiled.to_dict(),
            "execution": execution,
            "scheduler": execution.get("scheduler", {}),
        }
    except OntologyViolation as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/simulate")
async def ontology_runtime_simulate(body: dict = Body(default_factory=dict), tenant_id: str = Header("default", alias="X-Ontology-Tenant")):
    steps = body.get("steps", [])
    if not isinstance(steps, list):
        raise HTTPException(status_code=422, detail="steps must be a list")
    try:
        return _kernel_for(tenant_id).simulate(steps, ticks=int(body.get("ticks", 1)))
    except OntologyViolation as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/llm/action")
async def ontology_runtime_llm_action(body: dict = Body(...), tenant_id: str = Header("default", alias="X-Ontology-Tenant")):
    return _kernel_for(tenant_id).execute_llm_action(body)


@router.post("/reasoning/action")
async def ontology_runtime_reasoning_action(body: dict = Body(...), tenant_id: str = Header("default", alias="X-Ontology-Tenant")):
    return _kernel_for(tenant_id).reasoning.execute(body)


@router.post("/decision/decide")
async def ontology_runtime_decide(body: dict = Body(default_factory=dict), tenant_id: str = Header("default", alias="X-Ontology-Tenant")):
    try:
        return _kernel_for(tenant_id).decide(objective=str(body.get("objective", "BALANCED")), weights=body.get("weights"))
    except OntologyViolation as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/rl/optimize")
async def ontology_runtime_optimize_policy(body: dict = Body(default_factory=dict), tenant_id: str = Header("default", alias="X-Ontology-Tenant")):
    try:
        return _kernel_for(tenant_id).optimize_policy(rewards=body.get("rewards"))
    except OntologyViolation as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/ingest")
async def ontology_runtime_ingest(body: dict = Body(default_factory=dict), tenant_id: str = Header("default", alias="X-Ontology-Tenant")):
    try:
        kernel = _kernel_for(tenant_id)
        if "raw" in body:
            return kernel.ingest_raw_gw2(body["raw"])
        return kernel.ingest_normalized(body)
    except OntologyViolation as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/trace/{entity_id}")
async def ontology_runtime_trace(entity_id: str, depth: int = 2, tenant_id: str = Header("default", alias="X-Ontology-Tenant")):
    return _kernel_for(tenant_id).query().traverse(entity_id, depth=depth)


@router.get("/dependencies/{entity_id}")
async def ontology_runtime_dependencies(entity_id: str, tenant_id: str = Header("default", alias="X-Ontology-Tenant")):
    return {"dependencies": _kernel_for(tenant_id).query().dependencies(entity_id)}


@router.get("/lineage")
async def ontology_runtime_lineage(limit: int = 50, tenant_id: str = Header("default", alias="X-Ontology-Tenant")):
    return {"lineage": _kernel_for(tenant_id).lineage_store.list(limit=limit)}


@router.post("/replay")
async def ontology_runtime_replay(body: dict = Body(default_factory=dict), tenant_id: str = Header("default", alias="X-Ontology-Tenant")):
    kernel = _kernel_for(tenant_id)
    lineage = body.get("lineage") or kernel.snapshot()["lineage"]
    replay = kernel.replay(lineage)
    return {
        "deterministic": replay["deterministic"],
        "mismatches": replay["mismatches"],
        "state": replay["state"].to_dict(),
        "lineage": replay["lineage"],
    }
