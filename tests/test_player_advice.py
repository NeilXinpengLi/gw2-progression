from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from gw2_progression.advice import PlayerAdviceEngine, coin
from gw2_progression.api.main import app

GOLDEN = Path("data/knowledge_acquisition/player_craft_advice_20260629-233142.md")
FULL_FIXTURE = Path("data/knowledge_acquisition/account_craft_feasibility_250_20260629-233142.json")


def _fixture_report() -> dict:
    return {
        "run_id": "20260629-233142",
        "account_snapshot_path": "data\\account_snapshots\\gw2-account-Netro.7195-pre_play-20260629-220210.json",
        "account_name": "Netro.7195",
        "holding_summary": {"unique_item_ids": 1145, "total_item_count": 76431},
        "opportunity_count": 249,
        "profitable_count": 51,
        "executable_count": 64,
        "executable_profitable_count": 11,
        "top_executable_profitable": [
            {
                "account_rank": 1,
                "output_item_name": "Carrion Silk Insignia",
                "output_item_id": "19865",
                "net_profit": 187,
                "roi": 0.789,
                "craft_cost": 237,
                "account_feasibility": {"craftable_now": 273, "missing_total_count": 0, "requirements": []},
            },
            {
                "account_rank": 2,
                "output_item_name": "Darkvine Gauntlets",
                "output_item_id": "4907",
                "net_profit": 151,
                "roi": 1.1797,
                "craft_cost": 128,
                "account_feasibility": {"craftable_now": 36, "missing_total_count": 0, "requirements": []},
            },
        ],
        "top_executable": [
            {
                "output_item_name": "Carrion Silk Insignia",
                "output_item_id": "19865",
                "net_profit": 187,
                "roi": 0.789,
                "craft_cost": 237,
                "account_feasibility": {"craftable_now": 273, "missing_total_count": 0, "requirements": []},
            },
            {
                "output_item_name": "Cured Thin Leather Square",
                "output_item_id": "19738",
                "net_profit": 0,
                "roi": 0,
                "craft_cost": 12,
                "account_feasibility": {"craftable_now": 336, "missing_total_count": 0, "requirements": []},
            },
        ],
        "blocked_profitable_lowest_missing": [
            {
                "output_item_name": "Rampager's Embroidered Silk Insignia",
                "output_item_id": "19980",
                "net_profit": 449,
                "roi": 0.3915,
                "craft_cost": 1147,
                "account_feasibility": {
                    "craftable_now": 0,
                    "missing_total_count": 1,
                    "requirements": [{"item_id": "72194", "owned": 0, "required": 1, "missing": 1}],
                },
            },
            {
                "output_item_name": "Assassin's Darksteel Imbued Inscription",
                "output_item_id": "19950",
                "net_profit": 7323,
                "roi": 0.9194,
                "craft_cost": 7965,
                "account_feasibility": {"craftable_now": 0, "missing_total_count": 2, "requirements": []},
            },
        ],
    }


def _write_fixture(tmp_path: Path) -> Path:
    fixture = tmp_path / "account_craft_feasibility_fixture.json"
    fixture.write_text(json.dumps(_fixture_report()), encoding="utf-8")
    return fixture


def test_coin_formats_gw2_copper_values():
    assert coin(187) == "1s 87c"
    assert coin(7323) == "73s 23c"
    assert coin(-8) == "-8c"
    assert coin(10023) == "1g 0s 23c"


def test_player_advice_matches_golden_quality_sections(tmp_path):
    result = PlayerAdviceEngine().from_file(_write_fixture(tmp_path))
    markdown = result.markdown

    for heading in [
        "# GW2 Craft-vs-Buy Player Advice",
        "## Summary",
        "## Do Now",
        "## Almost Ready",
        "## High Profit But Blocked",
        "## Avoid For Now",
        "## Operational Notes",
    ]:
        assert heading in markdown

    for expected in [
        "- Total sampled opportunities: `249`",
        "- Profitable opportunities: `51`",
        "- Craftable with current account materials: `64`",
        "- Craftable and profitable now: `11`",
        "### 1. Carrion Silk Insignia",
        "- Net profit: `1s 87c`",
        "- Craftable now: `273`",
        "### Rampager's Embroidered Silk Insignia",
        "- `Cured Thin Leather Square`: net `0c`, craftable `336`",
    ]:
        assert expected in markdown


@pytest.mark.skipif(not (GOLDEN.exists() and FULL_FIXTURE.exists()), reason="local full golden report is generated under ignored data/")
def test_player_advice_local_full_golden_still_has_same_quality_gate():
    result = PlayerAdviceEngine().from_file(FULL_FIXTURE)
    markdown = result.markdown
    golden = GOLDEN.read_text(encoding="utf-8")

    for expected in [
        "### 1. Carrion Silk Insignia",
        "- Net profit: `1s 87c`",
        "- `Assassin's Darksteel Imbued Inscription`: profit `73s 23c`, missing `2`",
        "- `Cured Thin Leather Square`: net `0c`, craftable `336`",
    ]:
        assert expected in markdown
        assert expected in golden


def test_player_advice_result_writes_markdown_and_json(tmp_path):
    result = PlayerAdviceEngine().from_file(_write_fixture(tmp_path))
    paths = result.write(tmp_path)

    md = Path(paths["markdown_path"])
    data_path = Path(paths["json_path"])
    assert md.exists()
    assert data_path.exists()
    assert "## Do Now" in md.read_text(encoding="utf-8")
    data = json.loads(data_path.read_text(encoding="utf-8"))
    assert data["summary"]["executable_profitable_count"] == 11
    assert data["immediate_profitable"][0]["output_item_name"] == "Carrion Silk Insignia"


def test_player_advice_api_generates_report(tmp_path):
    fixture = _write_fixture(tmp_path)
    with TestClient(app) as client:
        response = client.post(
            "/advice/craft-vs-buy",
            json={
                "feasibility_report_path": str(fixture),
                "output_dir": str(tmp_path),
                "write_files": True,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["account_name"] == "Netro.7195"
    assert "## Almost Ready" in body["markdown"]
    assert body["data"]["summary"]["profitable_count"] == 51
    assert Path(body["files"]["markdown_path"]).exists()
