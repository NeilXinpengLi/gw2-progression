from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .routes.analyze import router as analyze_router

STATIC_DIR = Path(__file__).parent.parent / "static"

app = FastAPI(title="GW2 Progression", version="0.1.0")
app.include_router(analyze_router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
