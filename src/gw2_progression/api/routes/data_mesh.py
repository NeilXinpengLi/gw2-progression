from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from gw2_progression.data_mesh import (
    DataMeshBridge,
    DataIngestion,
    DataMeshPipeline,
    SchemaNormalizer,
    ConfidenceSystem,
    SourceRegistry,
    BUILTIN_SOURCES,
)

router = APIRouter(prefix="/mesh", tags=["data-mesh"])

_bridge = DataMeshBridge()


class IngestRequest(BaseModel):
    sources: list[dict]


class PipelineRequest(BaseModel):
    sources: list[dict]
    options: dict | None = None


class NormalizeRequest(BaseModel):
    data: dict
    source_type: str = "api"


class ConfidenceRequest(BaseModel):
    source_type: str
    source_id: str | None = None
    records_count: int = 1
    staleness_days: int = 0
    cross_validation_count: int = 0


@router.get("/status")
async def mesh_status():
    return _bridge.status()


@router.get("/health")
async def mesh_health():
    from gw2_progression.data_mesh.integration import check_mesh_health
    return check_mesh_health()


@router.post("/ingest")
async def ingest(body: IngestRequest):
    return _bridge.multi_source_ingest(body.sources)


@router.post("/pipeline")
async def pipeline(body: PipelineRequest):
    return _bridge.run_pipeline(body.sources, body.options)


@router.post("/normalize")
async def normalize(body: NormalizeRequest):
    ds = SchemaNormalizer.normalize(body.data, source_type=body.source_type)
    return ds.to_dict()


@router.post("/confidence")
async def confidence(body: ConfidenceRequest):
    cs = ConfidenceSystem()
    record = cs.evaluate(
        source_type=body.source_type,
        source_id=body.source_id,
        records_count=body.records_count,
        staleness_days=body.staleness_days,
        cross_validation_count=body.cross_validation_count,
    )
    return record.to_dict()


@router.get("/sources")
async def list_sources(
    source_type: str | None = Query(None, description="Filter by source type"),
    domain: str | None = Query(None, description="Filter by KB domain"),
):
    reg = SourceRegistry()
    for s in BUILTIN_SOURCES:
        reg.register(s)
    results = reg.list_sources()
    if source_type:
        from gw2_progression.data_mesh.sources.registry import SourceType
        try:
            st = SourceType(source_type)
            results = [s for s in results if s.source_type == st]
        except ValueError:
            raise HTTPException(400, f"unknown source_type: {source_type}")
    if domain:
        from gw2_progression.data_mesh.sources.registry import KBDomain
        try:
            d = KBDomain(domain)
            results = [s for s in results if s.recommended_kb_domain == d]
        except ValueError:
            raise HTTPException(400, f"unknown domain: {domain}")
    return [s.to_dict() for s in results]


@router.get("/sources/{source_id}")
async def get_source(source_id: str):
    reg = SourceRegistry()
    for s in BUILTIN_SOURCES:
        reg.register(s)
    source = reg.get(source_id)
    if source is None:
        raise HTTPException(404, f"source not found: {source_id}")
    return source.to_dict()


@router.get("/bridge")
async def bridge_status():
    return _bridge.multi_source_ingest([
        {"type": "static", "params": {
            "items": [{"id": 1, "name": "test"}],
            "wallet": [{"id": 1, "value": 100}],
        }},
    ])
