from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from gw2_progression.advice import PlayerAdviceEngine

router = APIRouter(prefix="/advice", tags=["advice"])


class CraftAdviceRequest(BaseModel):
    feasibility_report_path: str
    output_dir: str = "data/knowledge_acquisition"
    write_files: bool = True


@router.post("/craft-vs-buy")
async def craft_vs_buy_advice(req: CraftAdviceRequest) -> dict[str, Any]:
    path = Path(req.feasibility_report_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Feasibility report not found: {path}")
    result = PlayerAdviceEngine().from_file(path)
    payload: dict[str, Any] = {
        "account_name": result.account_name,
        "run_id": result.run_id,
        "markdown": result.markdown,
        "data": result.data,
    }
    if req.write_files:
        payload["files"] = result.write(req.output_dir)
    return payload
