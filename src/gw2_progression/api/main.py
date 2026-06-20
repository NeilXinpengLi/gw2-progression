import logging
import time
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from gw2_progression.database import init_db
from gw2_progression.gw2_client import Gw2ApiError
from gw2_progression.gw2_client import _close_client as close_gw2_client
from gw2_progression.services.price_service import close_client as close_price_client
from gw2_progression.services.price_service import warmup_price_cache
from gw2_progression.services.progression_service import seed_templates

from .routes.analyze import router as analyze_router
from .routes.crafting import router as crafting_router
from .routes.goals import router as goals_router
from .routes.progression import router as progression_router
from .routes.resolve import router as resolve_router
from .routes.valuation import router as valuation_router

STATIC_DIR = Path(__file__).parent.parent / "static"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("gw2")

RATE_LIMIT_REQUESTS = 30
RATE_LIMIT_WINDOW = 60
_rate_limit_buckets: dict[str, list] = defaultdict(list)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting GW2 Progression")
    await init_db()
    await warmup_price_cache()
    await seed_templates()
    yield
    logger.info("Shutting down GW2 Progression")
    await close_gw2_client()
    await close_price_client()


app = FastAPI(title="GW2 Progression", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    req_id = uuid.uuid4().hex[:8]
    start = time.monotonic()
    _metrics["requests"] += 1
    if request.url.path == "/analyze":
        _metrics["analyses"] += 1
    logger.info("[%s] %s %s", req_id, request.method, request.url.path)
    try:
        response = await call_next(request)
        elapsed = time.monotonic() - start
        logger.info("[%s] %s %s -> %d (%.2fs)", req_id, request.method, request.url.path, response.status_code, elapsed)
        response.headers["X-Request-ID"] = req_id
        if response.status_code >= 500:
            _metrics["errors"] += 1
        return response
    except Gw2ApiError as e:
        _metrics["errors"] += 1
        elapsed = time.monotonic() - start
        logger.warning("[%s] Gw2ApiError %d: %.60s (%.2fs)", req_id, e.status_code, e.message, elapsed)
        return JSONResponse(status_code=e.status_code, content={"detail": e.message})
    except Exception as e:
        _metrics["errors"] += 1
        elapsed = time.monotonic() - start
        logger.error("[%s] Unhandled: %s (%.2fs)", req_id, str(e), elapsed)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.url.path.startswith("/static") or request.url.path == "/health":
        return await call_next(request)

    client_ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    bucket = _rate_limit_buckets[client_ip]
    bucket[:] = [t for t in bucket if now - t < RATE_LIMIT_WINDOW]

    if len(bucket) >= RATE_LIMIT_REQUESTS:
        logger.warning("Rate limit exceeded for %s", client_ip)
        return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded. Try again later."})

    bucket.append(now)
    return await call_next(request)


app.include_router(analyze_router)
app.include_router(resolve_router)
app.include_router(valuation_router)
app.include_router(crafting_router)
app.include_router(goals_router)
app.include_router(progression_router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


_metrics = {"requests": 0, "analyses": 0, "errors": 0, "started_at": time.time()}


@app.get("/metrics")
async def metrics():
    elapsed = int(time.time() - _metrics["started_at"])
    return {
        "uptime_seconds": elapsed,
        "requests": _metrics["requests"],
        "analyses": _metrics["analyses"],
        "errors": _metrics["errors"],
        "status": "ok",
    }


_ws_clients: set = set()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    _ws_clients.add(websocket)
    try:
        await websocket.send_json({"type": "connected", "message": "GW2 Progression WebSocket connected"})
        while True:
            await websocket.receive_text()
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        _ws_clients.discard(websocket)
