from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from gw2_progression.advice import PlayerAdviceEngine

router = APIRouter(prefix="/advice", tags=["advice"])


class CraftAdviceRequest(BaseModel):
    feasibility_report_path: str
    output_dir: str = "data/knowledge_acquisition"
    write_files: bool = True
    player_goal: str = ""
    account_stage: str = ""
    snapshot_delta: dict[str, Any] = Field(default_factory=dict)
    market_risk: dict[str, Any] = Field(default_factory=dict)
    include_explanations: bool = False
    report_language: str = "en"
    llm_explanation_layer: str = "deterministic_template"
    llm_provider_key_file: str = ""
    llm_provider_model: str = ""
    llm_provider_limit: int = 3


@router.post("/craft-vs-buy")
async def craft_vs_buy_advice(req: CraftAdviceRequest) -> dict[str, Any]:
    path = Path(req.feasibility_report_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Feasibility report not found: {path}")
    result = PlayerAdviceEngine().from_file(
        path,
        context={
            "player_goal": req.player_goal,
            "account_stage": req.account_stage,
            "snapshot_delta": req.snapshot_delta,
            "market_risk": req.market_risk,
            "include_explanations": req.include_explanations,
            "report_language": req.report_language,
            "llm_explanation_layer": req.llm_explanation_layer,
            "llm_provider_key_file": req.llm_provider_key_file,
            "llm_provider_model": req.llm_provider_model,
            "llm_provider_limit": req.llm_provider_limit,
        },
    )
    payload: dict[str, Any] = {
        "account_name": result.account_name,
        "run_id": result.run_id,
        "markdown": result.markdown,
        "data": result.data,
    }
    if req.write_files:
        payload["files"] = result.write(req.output_dir)
    return payload
