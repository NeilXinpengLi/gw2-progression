import logging
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from gw2_progression.database import init_db
from gw2_progression.gw2_client import Gw2ApiError
from gw2_progression.gw2_client import _close_client as close_gw2_client
from gw2_progression.services.price_service import close_client as close_price_client
from gw2_progression.services.price_service import warmup_price_cache

from .routes.analyze import router as analyze_router
from .routes.crafting import router as crafting_router
from .routes.resolve import router as resolve_router
from .routes.valuation import router as valuation_router

STATIC_DIR = Path(__file__).parent.parent / "static"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("gw2")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting GW2 Progression")
    await init_db()
    await warmup_price_cache()
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
    logger.info("[%s] %s %s", req_id, request.method, request.url.path)
    try:
        response = await call_next(request)
        elapsed = time.monotonic() - start
        logger.info("[%s] %s %s -> %d (%.2fs)", req_id, request.method, request.url.path, response.status_code, elapsed)
        response.headers["X-Request-ID"] = req_id
        return response
    except Gw2ApiError as e:
        elapsed = time.monotonic() - start
        logger.warning("[%s] Gw2ApiError %d: %.60s (%.2fs)", req_id, e.status_code, e.message, elapsed)
        return JSONResponse(status_code=e.status_code, content={"detail": e.message})
    except Exception as e:
        elapsed = time.monotonic() - start
        logger.error("[%s] Unhandled: %s (%.2fs)", req_id, str(e), elapsed)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})


app.include_router(analyze_router)
app.include_router(resolve_router)
app.include_router(valuation_router)
app.include_router(crafting_router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
