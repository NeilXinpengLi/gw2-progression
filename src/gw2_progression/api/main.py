import json
import logging
import os
import time
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from gw2_progression.database import close_pool, init_db
from gw2_progression.gw2_client import Gw2ApiError
from gw2_progression.gw2_client import _close_client as close_gw2_client
from gw2_progression.logging_config import setup_logging
from gw2_progression.metrics import metrics
from gw2_progression.services.auth_service import SESSION_TTL, create_session, delete_session, get_api_key, list_sessions
from gw2_progression.services.price_service import close_client as close_price_client
from gw2_progression.services.price_service import warmup_price_cache
from gw2_progression.services.product_service import seed_products
from gw2_progression.services.progression_service import seed_templates
from gw2_progression.services.provider_service import seed_providers

from .routes.affiliates import router as affiliates_router
from .routes.agent import router as agent_router
from .routes.analyze import router as analyze_router
from .routes.audit import router as audit_router
from .routes.builds import router as builds_router
from .routes.commerce import router as commerce_router
from .routes.crafting import router as crafting_router
from .routes.credentials import router as credentials_router
from .routes.engine import router as engine_router
from .routes.goals import router as goals_router
from .routes.guild import router as guild_router
from .routes.payment import router as payment_router
from .routes.production import router as production_router
from .routes.progression import router as progression_router
from .routes.quests import router as quests_router
from .routes.reports import router as reports_router
from .routes.resolve import router as resolve_router
from .routes.subscriptions import router as subscriptions_router
from .routes.tp_strategy import router as tp_router
from .routes.v4 import router as v4_router
from .routes.v5 import router as v5_router
from .routes.valuation import router as valuation_router
from .routes.workspaces import router as workspaces_router

STATIC_DIR = Path(__file__).parent.parent / "static"

setup_logging()
logger = logging.getLogger("gw2")

RATE_LIMIT_REQUESTS = int(os.environ.get("RATE_LIMIT_REQUESTS", "30"))
RATE_LIMIT_WINDOW = int(os.environ.get("RATE_LIMIT_WINDOW", "60"))
_rate_limit_buckets: dict[str, list] = defaultdict(list)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting GW2 Progression")
    await init_db()
    await warmup_price_cache()
    await seed_templates()
    await seed_products()
    await seed_providers()
    # Process pending delivery jobs
    try:
        from gw2_progression.services.commerce_service import process_pending_deliveries

        await process_pending_deliveries()
    except Exception as e:
        logger.warning("Delivery processing failed: %s", e)
    yield
    logger.info("Shutting down GW2 Progression")
    await close_gw2_client()
    await close_price_client()
    await close_pool()


app = FastAPI(title="GW2 Progression", version="0.1.0", lifespan=lifespan)

# CORS — restrict in production via CORS_ORIGINS env var
_cors_origins = os.environ.get("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins if _cors_origins != ["*"] else ["*"],
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    allow_credentials=True,
)


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "no-referrer-when-downgrade"
    if os.environ.get("ENV", "development") == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    req_id = uuid.uuid4().hex[:8]
    start = time.monotonic()
    metrics.requests_active += 1
    metrics.requests_total += 1
    if request.url.path == "/analyze":
        metrics.analyses_total += 1

    try:
        response = await call_next(request)
        elapsed_ms = (time.monotonic() - start) * 1000
        is_error = response.status_code >= 500
        metrics.record_request(request.url.path, elapsed_ms, is_error)
        logger.info(
            "%s %s -> %d (%.0fms)",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
            extra={"request_id": req_id, "duration_ms": round(elapsed_ms, 1), "path": request.url.path, "status_code": response.status_code},
        )
        response.headers["X-Request-ID"] = req_id
        return response
    except Gw2ApiError as e:
        metrics.errors_total += 1
        elapsed_ms = (time.monotonic() - start) * 1000
        logger.warning("Gw2ApiError %d: %.60s (%.0fms)", e.status_code, e.message, elapsed_ms, extra={"request_id": req_id, "duration_ms": round(elapsed_ms, 1)})
        return JSONResponse(status_code=e.status_code, content={"detail": e.message})
    except Exception as e:
        metrics.errors_total += 1
        elapsed_ms = (time.monotonic() - start) * 1000
        logger.exception("Unhandled: %s (%.0fms)", str(e), elapsed_ms, extra={"request_id": req_id, "duration_ms": round(elapsed_ms, 1)})
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})
    finally:
        metrics.requests_active -= 1


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
app.include_router(reports_router)
app.include_router(resolve_router)
app.include_router(valuation_router)
app.include_router(crafting_router)
app.include_router(goals_router)
app.include_router(guild_router)
app.include_router(progression_router)
app.include_router(quests_router)
app.include_router(tp_router)
app.include_router(builds_router)
app.include_router(commerce_router)
app.include_router(credentials_router)
app.include_router(affiliates_router)
app.include_router(engine_router)
app.include_router(audit_router)
app.include_router(workspaces_router)
app.include_router(v4_router)
app.include_router(v5_router)
app.include_router(production_router)
app.include_router(payment_router)
app.include_router(agent_router)
app.include_router(subscriptions_router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.post("/auth/session")
async def create_session_endpoint(api_key: str = Body(...)):
    from gw2_progression.analyzer import fetch_all
    from gw2_progression.services.audit_service import record_audit

    try:
        contents = await fetch_all(api_key)
        token = await create_session(api_key, contents.account_name or "unknown")
        await record_audit(actor=contents.account_name or "unknown", action="session.create", resource="auth", detail="Session created", success=True)
        return {"token": token, "account_name": contents.account_name, "expires_in": SESSION_TTL}
    except Gw2ApiError as e:
        await record_audit(action="session.create", resource="auth", detail=f"Failed: {e.message}", success=False)
        raise HTTPException(status_code=401, detail=e.message)


@app.get("/auth/sessions")
async def list_sessions_endpoint():
    sessions = await list_sessions()
    return sessions


@app.delete("/auth/session/{token}")
async def delete_session_endpoint(token: str):
    from gw2_progression.services.audit_service import record_audit

    deleted = await delete_session(token)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    await record_audit(action="session.delete", resource="auth", detail=f"Token {token[:8]}...")
    return {"status": "deleted"}


# Inject API key from session token into requests
@app.middleware("http")
async def session_middleware(request: Request, call_next):
    if request.url.path in ("/analyze", "/value/analyze") and request.method == "POST":
        try:
            body = await request.json()
            key = body.get("api_key", "")
            resolved = await get_api_key(key)
            if resolved != key:
                body["api_key"] = resolved
                request._body = json.dumps(body).encode()
        except Exception:
            pass
    return await call_next(request)


@app.get("/health")
async def health():
    db_ok = False
    try:
        from gw2_progression.database import get_db, release_db

        conn = await get_db()
        await conn.execute("SELECT 1")
        await release_db(conn)
        db_ok = True
    except Exception:
        pass
    return {
        "status": "ok" if db_ok else "degraded",
        "db": "ok" if db_ok else "error",
        "uptime": int(time.time() - metrics.started_at),
    }


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/metrics")
async def get_metrics():
    return metrics.snapshot()


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
