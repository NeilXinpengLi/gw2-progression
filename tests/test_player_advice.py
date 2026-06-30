from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from gw2_progression.advice import PlayerAdviceEngine, coin
from gw2_progression.api.main import app
from gw2_progression.api.routes.advice import CraftAdviceRequest, craft_vs_buy_advice

GOLDEN = Path("data/knowledge_acquisition/player_craft_advice_20260629-233142.md")
FULL_FIXTURE = Path("data/knowledge_acquisition/account_craft_feasibility_250_20260629-233142.json")


class FakeExpertLayer:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def explain_decision(self, decision: dict, context: dict | None = None, use_provider: bool = False) -> dict:
        self.calls.append({"decision": decision, "context": context, "use_provider": use_provider})
        item_name = decision["facts"]["output_item_name"]
        return {
            "provider": "openai_compatible",
            "mode": "read_only",
            "config": {"configured": True, "model": "fake-real-provider"},
            "explanation": {
                "content": json.dumps(
                    {
                        "guidance": (
                            f"{item_name} fits this player's current goal: it can be crafted 273 time(s), "
                            "sample net profit is 1s 87c with ROI 0.789, market risk is low, and a small first craft is recommended."
                        )
                    },
                    ensure_ascii=False,
                )
            },
        }


class BadCurrencyExpertLayer:
    def explain_decision(self, decision: dict, context: dict | None = None, use_provider: bool = False) -> dict:
        return {
            "provider": "openai_compatible",
            "mode": "read_only",
            "config": {"configured": True, "model": "bad-currency-model"},
            "explanation": {"content": json.dumps({"guidance": "该物品每次可赚1金87铜，低风险，建议直接大量制作。"}, ensure_ascii=False)},
        }


class PartialButValidExpertLayer:
    def explain_decision(self, decision: dict, context: dict | None = None, use_provider: bool = False) -> dict:
        return {
            "provider": "openai_compatible",
            "mode": "read_only",
            "config": {"configured": True, "model": "partial-model"},
            "explanation": {
                "content": "Crafting Carrion Silk Insignia fits your beginner gold goal with 1s 87c net profit and low market risk."
            },
        }


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


def test_player_advice_context_adds_goal_stage_delta_risk_and_explanations(tmp_path):
    result = PlayerAdviceEngine().from_file(
        _write_fixture(tmp_path),
        context={
            "player_goal": "gold_profit",
            "account_stage": "beginner",
            "snapshot_delta": {"gold_delta_copper": 12345, "material_item_delta": 3, "snapshot_count": 2},
            "market_risk": {
                "items": {
                    "19865": {"level": "low", "reason": "stable sample spread"},
                    "19980": "medium",
                }
            },
            "include_explanations": True,
        },
    )

    markdown = result.markdown
    data = result.data
    first = data["immediate_profitable"][0]

    assert "## Player Context" in markdown
    assert "- Goal: `gold_profit`" in markdown
    assert "- Account stage: `beginner`" in markdown
    assert "- Why it fits:" in markdown
    assert "- Risk: `low` (stable sample spread)" in markdown
    assert data["player_context"]["include_explanations"] is True
    assert first["advice_explanation"]["goal_fit"] == "strong"
    assert first["advice_explanation"]["market_risk"]["level"] == "low"
    assert first["advice_explanation"]["llm_prompt_facts"]["player_goal"] == "gold_profit"


def test_player_advice_api_accepts_explanation_context(tmp_path):
    fixture = _write_fixture(tmp_path)
    body = asyncio.run(
        craft_vs_buy_advice(
            CraftAdviceRequest(
                feasibility_report_path=str(fixture),
                output_dir=str(tmp_path),
                write_files=False,
                player_goal="beginner_gold",
                account_stage="beginner",
                snapshot_delta={"gold_delta_copper": 5000},
                market_risk={"default": "medium"},
                include_explanations=True,
            )
        )
    )

    assert "## Player Context" in body["markdown"]
    assert "Why it fits" in body["markdown"]
    assert body["data"]["player_context"]["player_goal"] == "beginner_gold"
    assert body["data"]["immediate_profitable"][0]["advice_explanation"]["market_risk"]["level"] == "medium"


def test_player_advice_uses_llm_provider_layer_with_fact_constraints(tmp_path):
    expert = FakeExpertLayer()
    result = PlayerAdviceEngine(expert_layer=expert).from_file(
        _write_fixture(tmp_path),
        context={
            "player_goal": "gold_profit",
            "account_stage": "beginner",
            "include_explanations": True,
            "llm_explanation_layer": "provider",
            "llm_provider_key_file": "D:/secret/provider-key.txt",
            "llm_provider_model": "agnes-2.0-flash",
            "llm_provider_limit": 1,
        },
    )

    first = result.data["immediate_profitable"][0]["advice_explanation"]
    second = result.data["immediate_profitable"][1]["advice_explanation"]

    assert len(expert.calls) == 1
    assert expert.calls[0]["use_provider"] is True
    assert "Do not change item names" in expert.calls[0]["decision"]["constraints"][0]
    assert first["llm_provider"]["provider"] == "openai_compatible"
    assert first["llm_provider"]["configured"] is True
    assert first["llm_provider"]["model"] == "fake-real-provider"
    assert first["expert_note"].startswith("Carrion Silk Insignia fits this player's current goal")
    assert not first["expert_note"].startswith("{")
    assert first["expert_note_source"] == "provider"
    assert first["gold_standard_alignment"]["passed"] is True
    assert second["llm_provider"]["mode"] == "not_requested"
    assert "Expert note:" in result.markdown
    assert "provider-key" not in json.dumps(result.data)
    assert result.data["player_context"]["llm_provider_model"] == "agnes-2.0-flash"


def test_player_advice_rejects_llm_note_that_changes_profit_scale(tmp_path):
    result = PlayerAdviceEngine(expert_layer=BadCurrencyExpertLayer()).from_file(
        _write_fixture(tmp_path),
        context={
            "player_goal": "gold_profit",
            "account_stage": "beginner",
            "include_explanations": True,
            "llm_explanation_layer": "provider",
            "llm_provider_limit": 1,
        },
    )

    explanation = result.data["immediate_profitable"][0]["advice_explanation"]

    assert explanation["llm_provider"]["validation"]["passed"] is False
    assert "no_profit_currency_scale_error" in explanation["llm_provider"]["validation"]["violations"]
    assert "1金87铜" not in explanation["expert_note"]
    assert "1s 87c" in explanation["expert_note"]
    assert "small first craft" in explanation["expert_note"]
    assert explanation["expert_note_source"] == "codex_style_fallback"
    assert explanation["gold_standard_alignment"]["passed"] is True


def test_player_advice_rejects_provider_note_that_misses_gold_standard_facts(tmp_path):
    result = PlayerAdviceEngine(expert_layer=PartialButValidExpertLayer()).from_file(
        _write_fixture(tmp_path),
        context={
            "player_goal": "gold_profit",
            "account_stage": "beginner",
            "include_explanations": True,
            "llm_explanation_layer": "provider",
            "llm_provider_limit": 1,
        },
    )

    explanation = result.data["immediate_profitable"][0]["advice_explanation"]

    assert explanation["llm_provider"]["validation"]["passed"] is False
    assert "craftable_preserved" in explanation["llm_provider"]["validation"]["violations"]
    assert "roi_preserved" in explanation["llm_provider"]["validation"]["violations"]
    assert explanation["expert_note_source"] == "codex_style_fallback"
    assert "273" in explanation["expert_note"]
    assert "ROI 0.789" in explanation["expert_note"]
    assert explanation["gold_standard_alignment"]["passed"] is True


def test_player_advice_can_explicitly_render_chinese_fallback(tmp_path):
    result = PlayerAdviceEngine(expert_layer=BadCurrencyExpertLayer()).from_file(
        _write_fixture(tmp_path),
        context={
            "player_goal": "gold_profit",
            "account_stage": "beginner",
            "include_explanations": True,
            "report_language": "zh",
            "llm_explanation_layer": "provider",
            "llm_provider_limit": 1,
        },
    )

    note = result.data["immediate_profitable"][0]["advice_explanation"]["expert_note"]

    assert "适合先做小额尝试" in note
    assert "1s 87c" in note


def test_player_advice_reclassifies_unsorted_new_input_and_avoids_bad_recommendations():
    report = _fixture_report()
    report["top_executable_profitable"] = [
        {
            "account_rank": 99,
            "output_item_name": "Blocked Profit Trap",
            "output_item_id": "9001",
            "net_profit": 9999,
            "roi": 9.9,
            "craft_cost": 1,
            "account_executable_score": 9999,
            "account_feasibility": {"craftable_now": 0, "missing_total_count": 2, "requirements": []},
        },
        {
            "account_rank": 3,
            "output_item_name": "Loss Trap",
            "output_item_id": "9002",
            "net_profit": -50,
            "roi": -0.1,
            "craft_cost": 500,
            "account_executable_score": 1000,
            "account_feasibility": {"craftable_now": 20, "missing_total_count": 0, "requirements": []},
        },
        {
            "account_rank": 2,
            "output_item_name": "Good But Lower",
            "output_item_id": "9003",
            "net_profit": 100,
            "roi": 0.5,
            "craft_cost": 200,
            "account_executable_score": 125,
            "account_feasibility": {"craftable_now": 10, "missing_total_count": 0, "requirements": []},
        },
        {
            "account_rank": 1,
            "output_item_name": "Best Real Action",
            "output_item_id": "9004",
            "net_profit": 200,
            "roi": 0.6,
            "craft_cost": 300,
            "account_executable_score": 300,
            "account_feasibility": {"craftable_now": 5, "missing_total_count": 0, "requirements": []},
        },
    ]
    report["top_executable"] = report["top_executable_profitable"] + report["top_executable"]
    report["blocked_profitable_lowest_missing"] = [
        {
            "output_item_name": "Far Blocked",
            "output_item_id": "9010",
            "net_profit": 5000,
            "roi": 1.2,
            "craft_cost": 1000,
            "account_feasibility": {"craftable_now": 0, "missing_total_count": 5, "requirements": []},
        },
        {
            "output_item_name": "Close Blocked",
            "output_item_id": "9011",
            "net_profit": 300,
            "roi": 0.8,
            "craft_cost": 500,
            "account_feasibility": {
                "craftable_now": 0,
                "missing_total_count": 1,
                "requirements": [{"item_id": "1", "owned": 0, "required": 1, "missing": 1}],
            },
        },
    ]

    result = PlayerAdviceEngine().from_report(report)
    data = result.data
    markdown = result.markdown

    assert data["quality_checks"]["passed"] is True
    assert data["immediate_profitable"][0]["output_item_name"] == "Best Real Action"
    assert all(row["output_item_name"] != "Blocked Profit Trap" for row in data["immediate_profitable"])
    assert all(row["output_item_name"] != "Loss Trap" for row in data["immediate_profitable"])
    assert data["near_blocked_profitable"][0]["output_item_name"] == "Close Blocked"
    assert "### 99. Blocked Profit Trap" not in markdown
    assert "### 3. Loss Trap" not in markdown
    assert "## Avoid For Now" in markdown
