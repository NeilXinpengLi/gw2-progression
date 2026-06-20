from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from gw2_progression.gw2_client import _close_client

from .routes.analyze import router as analyze_router

STATIC_DIR = Path(__file__).parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await _close_client()


app = FastAPI(title="GW2 Progression", version="0.1.0", lifespan=lifespan)
app.include_router(analyze_router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
