from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from gw2_progression.cognitive_os.engine import get_cognitive_os

router = APIRouter(prefix="/cognitive-os", tags=["cognitive_os"])


class InitializeRequest(BaseModel):
    gold: float = 0.0
    inventory: dict[str, int] = {}
    achievements: list[str] = []
    market: dict[str, dict[str, float]] = {}


class StepRequest(BaseModel):
    action_type: str | None = None
    item_id: str | None = None
    quantity: int = 1


class TrainRequest(BaseModel):
    episodes: int = 100
    max_steps: int = 50


class SimulateRequest(BaseModel):
    steps: int = 20
    mode: str = "auto"
    gold: float = 100.0
    inventory: dict[str, int] = {}


class MultiWorldRequest(BaseModel):
    num_worlds: int = 5
    steps: int = 20
    gold: float = 100.0
    inventory: dict[str, int] = {}


class CalibrateRequest(BaseModel):
    gold: float | None = None
    inventory: dict[str, int] | None = None
    achievements: list[str] | None = None


class CounterfactualRequest(BaseModel):
    original_action_type: str = "farm"
    original_item_id: str = "gold"
    alternative_action_type: str = "trade"
    alternative_item_id: str = "mystic_coin"


@router.post("/initialize")
async def initialize(req: InitializeRequest) -> dict[str, Any]:
    os = get_cognitive_os()
    os.initialize({
        "gold": req.gold,
        "inventory": dict(req.inventory),
        "achievements": list(req.achievements),
        "market": dict(req.market),
    })
    return {"status": "ok", "t": os.temporal.t, "agents": {n: a.to_dict() for n, a in os.agents.items()}}


@router.post("/step")
async def step(req: StepRequest) -> dict[str, Any]:
    os = get_cognitive_os()
    action = None
    if req.action_type:
        action = {"type": req.action_type, "item_id": req.item_id or "", "quantity": req.quantity}
    result = os.step(action)
    return result


@router.get("/analyze")
async def analyze() -> dict[str, Any]:
    os = get_cognitive_os()
    return os.analyze()


@router.post("/simulate")
async def simulate(req: SimulateRequest) -> dict[str, Any]:
    os = get_cognitive_os()
    initial_state = {
        "gold": req.gold,
        "inventory": dict(req.inventory),
        "achievements": [],
        "market": {},
    }
    return os.run_simulation(initial_state=initial_state, steps=req.steps, mode=req.mode)


@router.post("/train")
async def train(req: TrainRequest) -> dict[str, Any]:
    os = get_cognitive_os()
    return os.train(episodes=req.episodes, max_steps=req.max_steps)


@router.post("/agent-interact")
async def agent_interact() -> dict[str, Any]:
    os = get_cognitive_os()
    return os.agent_interact(os.temporal.current)


@router.post("/probabilistic-step")
async def probabilistic_step() -> dict[str, Any]:
    os = get_cognitive_os()
    return os.probabilistic_step()


@router.post("/multi-world")
async def multi_world(req: MultiWorldRequest) -> dict[str, Any]:
    os = get_cognitive_os()
    initial_state = {
        "gold": req.gold,
        "inventory": dict(req.inventory),
        "achievements": [],
        "market": {},
    }
    os.initialize(initial_state)
    return os.run_multi_world(num_worlds=req.num_worlds, steps=req.steps)


@router.post("/calibrate")
async def calibrate(req: CalibrateRequest) -> dict[str, Any]:
    os = get_cognitive_os()
    target = {}
    if req.gold is not None:
        target["gold"] = req.gold
    if req.inventory is not None:
        target["inventory"] = dict(req.inventory)
    if req.achievements is not None:
        target["achievements"] = list(req.achievements)
    return os.calibrate(target if any((req.gold is not None, req.inventory is not None, req.achievements is not None)) else None)


@router.get("/behavior")
async def behavior() -> dict[str, Any]:
    os = get_cognitive_os()
    return os.classify_behavior()


@router.get("/gnn-induction")
async def gnn_induction() -> dict[str, Any]:
    os = get_cognitive_os()
    return os.gnn_induction()


@router.post("/counterfactual")
async def counterfactual(req: CounterfactualRequest) -> dict[str, Any]:
    os = get_cognitive_os()
    original = {"type": req.original_action_type, "item_id": req.original_item_id, "quantity": 1}
    alternative = {"type": req.alternative_action_type, "item_id": req.alternative_item_id, "quantity": 1}
    return os.counterfactual_query(original, alternative)


@router.get("/cognition-graph")
async def cognition_graph() -> dict[str, Any]:
    os = get_cognitive_os()
    return os.cognition.to_dict()


@router.get("/economy")
async def economy() -> dict[str, Any]:
    os = get_cognitive_os()
    return os.economy.to_dict()


@router.get("/policy")
async def policy() -> dict[str, Any]:
    os = get_cognitive_os()
    return os.policy.to_dict()


@router.get("/status")
async def status() -> dict[str, Any]:
    os = get_cognitive_os()
    return {
        "initialized": os._initialized,
        "t": os.temporal.t,
        "policy": os.policy.to_dict(),
        "learning": os.learning_loop.status(),
        "economy_health": os.economy.market_health(),
        "agents": {n: a.to_dict() for n, a in os.agents.items()},
        "cognition_graph_stats": os.cognition.to_dict()["stats"],
        "behavior_model": {
            "profile_count": len(os.behavior_model.profiles),
            "population_distribution": os.behavior_model.population_distribution(),
        },
        "calibration": {
            "average_loss": os.calibration.average_loss,
            "loss_trend": os.calibration.loss_trend,
        },
        "probabilistic": {
            "world_samples": len(os.probabilistic_world.samples),
            "dgsk_nodes": len(os.probabilistic_dgsk.nodes),
            "dgsk_edges": len(os.probabilistic_dgsk.edges),
        },
        "data_acquisition": {
            "sources": len(os.source_registry.get_enabled()),
            "graph_nodes": len(os.graph_builder.graph.get("nodes", {})),
            "stream_buffered": os.stream_engine.buffer_size_current,
            "scheduled_tasks": len(os.task_scheduler.tasks),
        },
        "data_factory": {
            "flywheel_iterations": os.data_factory.flywheel.iteration_count,
            "running": os.data_factory.flywheel._running,
            "datasets": os.dataset_builder.total_samples(),
        },
    }


# ─── Data Acquisition OS API ──────────────────────────────────────


class RegisterSourceRequest(BaseModel):
    id: str
    type: str = "api"
    priority: int = 2
    frequency: str = "daily"
    endpoint: str = ""


class StreamDataRequest(BaseModel):
    source_id: str = "custom"
    data_type: str = "custom"
    data: dict[str, Any] = {}


@router.post("/data/ingest")
async def ingest(source_id: str | None = None) -> dict[str, Any]:
    os_engine = get_cognitive_os()
    return os_engine.ingest_source(source_id)


@router.post("/data/register-source")
async def register_source(req: RegisterSourceRequest) -> dict[str, Any]:
    os_engine = get_cognitive_os()
    return os_engine.register_source(req.model_dump())


@router.get("/data/sources")
async def data_sources() -> dict[str, Any]:
    os_engine = get_cognitive_os()
    return os_engine.get_source_registry()


@router.post("/data/stream")
async def stream_data(req: StreamDataRequest) -> dict[str, Any]:
    os_engine = get_cognitive_os()
    return os_engine.stream_data(req.source_id, req.data_type, req.data)


@router.post("/data/flush")
async def flush_stream() -> dict[str, Any]:
    os_engine = get_cognitive_os()
    return os_engine.flush_stream()


@router.post("/data/scheduler/run")
async def run_scheduler() -> dict[str, Any]:
    os_engine = get_cognitive_os()
    return os_engine.run_scheduler()


@router.get("/data/scheduler")
async def scheduler_status() -> dict[str, Any]:
    os_engine = get_cognitive_os()
    return os_engine.task_scheduler.to_dict()


@router.get("/data/graph-builder")
async def graph_builder() -> dict[str, Any]:
    os_engine = get_cognitive_os()
    return os_engine.get_graph_builder_status()


# ─── Data Factory API ─────────────────────────────────────────────


class FlywheelRequest(BaseModel):
    iterations: int = 1


@router.post("/factory/start")
async def factory_start() -> dict[str, Any]:
    os_engine = get_cognitive_os()
    os_engine.data_factory.start()
    return {"status": "started"}


@router.post("/factory/stop")
async def factory_stop() -> dict[str, Any]:
    os_engine = get_cognitive_os()
    os_engine.data_factory.stop()
    return {"status": "stopped"}


@router.post("/factory/flywheel")
async def factory_flywheel(req: FlywheelRequest) -> dict[str, Any]:
    os_engine = get_cognitive_os()
    return os_engine.run_flywheel(iterations=req.iterations)


@router.get("/factory/status")
async def factory_status() -> dict[str, Any]:
    os_engine = get_cognitive_os()
    return os_engine.factory_status()


@router.post("/factory/generate-datasets")
async def factory_generate_datasets() -> dict[str, Any]:
    os_engine = get_cognitive_os()
    return os_engine.generate_datasets()
