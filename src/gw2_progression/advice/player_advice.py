from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from gw2_progression.expert_ai.expert_layer import LLMExpertLayer, LLMProviderConfig
from gw2_progression.ontology.explanation_constraints import (
    build_explanation_facts,
    normalize_language,
    validate_explanation_candidate,
)


def coin(copper: int) -> str:
    sign = "-" if copper < 0 else ""
    copper = abs(int(copper))
    gold, rem = divmod(copper, 10000)
    silver, copper = divmod(rem, 100)
    if gold:
        return f"{sign}{gold}g {silver}s {copper}c"
    if silver:
        return f"{sign}{silver}s {copper}c"
    return f"{sign}{copper}c"


@dataclass(frozen=True)
class PlayerAdviceResult:
    source_report: str
    account_name: str
    run_id: str
    markdown: str
    data: dict[str, Any]

    def write(self, output_dir: str | Path) -> dict[str, str]:
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        md_path = out_dir / f"player_craft_advice_{self.run_id}.md"
        json_path = out_dir / f"player_craft_advice_{self.run_id}.json"
        md_path.write_text(self.markdown, encoding="utf-8")
        json_path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"markdown_path": str(md_path), "json_path": str(json_path)}


@dataclass(frozen=True)
class PlayerAdviceContext:
    player_goal: str = ""
    account_stage: str = ""
    snapshot_delta: dict[str, Any] | None = None
    market_risk: dict[str, Any] | None = None
    include_explanations: bool = False
    report_language: str = "en"
    llm_explanation_layer: str = "deterministic_template"
    llm_provider_key_file: str = ""
    llm_provider_model: str = ""
    llm_provider_limit: int = 3


class PlayerAdviceEngine:
    """Converts account-aware craft feasibility data into player-facing advice."""

    def __init__(self, expert_layer: LLMExpertLayer | None = None) -> None:
        self.expert_layer = expert_layer

    def from_file(
        self,
        feasibility_report_path: str | Path,
        context: PlayerAdviceContext | dict[str, Any] | None = None,
    ) -> PlayerAdviceResult:
        path = Path(feasibility_report_path)
        report = json.loads(path.read_text(encoding="utf-8"))
        return self.from_report(report, source_report=str(path), context=context)

    def from_report(
        self,
        report: dict[str, Any],
        source_report: str = "",
        context: PlayerAdviceContext | dict[str, Any] | None = None,
    ) -> PlayerAdviceResult:
        run_id = str(report.get("run_id", "unknown"))
        account_name = str(report.get("account_name", "unknown"))
        player_context = self._normalize_context(report, context)
        llm_budget = {"remaining": self._int(player_context.get("llm_provider_limit"), default=3)}
        immediate = self._with_explanations(
            self._rank_immediate(report.get("top_executable_profitable", [])),
            category="do_now",
            context=player_context,
            llm_budget=llm_budget,
        )
        blocked = self._rank_blocked(report.get("blocked_profitable_lowest_missing", []))

        low_profit_executable = self._with_explanations(
            [
                row for row in self._as_rows(report.get("top_executable", []))
                if self._craftable_now(row) > 0 and self._int(row.get("net_profit")) <= 0
            ][:10],
            category="avoid",
            context=player_context,
            llm_budget=llm_budget,
        )
        near_blocked = self._with_explanations(
            [
                row
                for row in blocked
                if self._missing_total(row) <= 3
            ][:15],
            category="almost_ready",
            context=player_context,
            llm_budget=llm_budget,
        )
        high_profit_blocked = self._with_explanations(sorted(
            [row for row in blocked if self._int(row.get("net_profit")) > 500],
            key=lambda row: self._int(row.get("net_profit")),
            reverse=True,
        )[:10], category="high_profit_blocked", context=player_context, llm_budget=llm_budget)
        quality_checks = self.quality_checks(
            immediate=immediate,
            near_blocked=near_blocked,
            high_profit_blocked=high_profit_blocked,
            low_profit_executable=low_profit_executable,
        )

        data = {
            "source_report": source_report,
            "account_name": account_name,
            "holding_summary": report.get("holding_summary", {}),
            "player_context": self._public_context(player_context),
            "decision_policy": {
                "do_now": "craftable_now > 0 and net_profit > 0, sorted by account_executable_score/base_score/net_profit/roi",
                "almost_ready": "blocked profitable opportunities with missing_total_count <= 3, sorted by missing count then profit",
                "high_profit_blocked": "blocked opportunities with net_profit > 500, sorted by profit",
                "avoid_for_now": "craftable_now > 0 and net_profit <= 0",
                "explanation_layer": "context-aware deterministic explanation; external LLM may rewrite copy but must preserve category, risk, and numeric facts",
            },
            "quality_checks": quality_checks,
            "summary": {
                "opportunity_count": report.get("opportunity_count", 0),
                "profitable_count": report.get("profitable_count", 0),
                "executable_count": report.get("executable_count", 0),
                "executable_profitable_count": report.get("executable_profitable_count", 0),
            },
            "immediate_profitable": immediate,
            "near_blocked_profitable": near_blocked,
            "high_profit_blocked": high_profit_blocked,
            "low_profit_executable": low_profit_executable,
        }
        markdown = self.render_markdown(report, data)
        return PlayerAdviceResult(
            source_report=source_report,
            account_name=account_name,
            run_id=run_id,
            markdown=markdown,
            data=data,
        )

    def quality_checks(
        self,
        *,
        immediate: list[dict[str, Any]],
        near_blocked: list[dict[str, Any]],
        high_profit_blocked: list[dict[str, Any]],
        low_profit_executable: list[dict[str, Any]],
    ) -> dict[str, Any]:
        violations: list[str] = []
        if any(self._craftable_now(row) <= 0 or self._int(row.get("net_profit")) <= 0 for row in immediate):
            violations.append("do_now_contains_blocked_or_unprofitable")
        if any(self._craftable_now(row) > 0 for row in near_blocked):
            violations.append("almost_ready_contains_immediately_craftable")
        if any(self._missing_total(row) <= 0 for row in high_profit_blocked):
            violations.append("high_profit_blocked_contains_unblocked_item")
        if any(self._int(row.get("net_profit")) > 0 for row in low_profit_executable):
            violations.append("avoid_for_now_contains_profitable_item")
        return {
            "passed": not violations,
            "violations": violations,
            "counts": {
                "do_now": len(immediate),
                "almost_ready": len(near_blocked),
                "high_profit_blocked": len(high_profit_blocked),
                "avoid_for_now": len(low_profit_executable),
            },
        }

    def render_markdown(self, report: dict[str, Any], data: dict[str, Any]) -> str:
        lines: list[str] = []
        account_name = data.get("account_name", "unknown")
        run_id = str(report.get("run_id", "unknown"))
        holding = data.get("holding_summary", {})
        summary = data["summary"]

        lines.append("# GW2 Craft-vs-Buy Player Advice")
        lines.append("")
        lines.append(f"Account: `{account_name}`")
        lines.append(f"Source snapshot: `{report.get('account_snapshot_path', '')}`")
        lines.append(f"Run id: `{run_id}`")
        lines.append("")
        lines.append("## Summary")
        lines.append("")
        lines.append(f"- Total sampled opportunities: `{summary['opportunity_count']}`")
        lines.append(f"- Profitable opportunities: `{summary['profitable_count']}`")
        lines.append(f"- Craftable with current account materials: `{summary['executable_count']}`")
        lines.append(f"- Craftable and profitable now: `{summary['executable_profitable_count']}`")
        lines.append(f"- Account holdings scanned: `{holding.get('unique_item_ids')}` unique item ids, `{holding.get('total_item_count')}` total count")
        lines.append("")

        if self._include_explanations(data):
            self._append_player_context(lines, data)
        self._append_do_now(lines, data.get("immediate_profitable", []))
        self._append_almost_ready(lines, data.get("near_blocked_profitable", []))
        self._append_high_profit_blocked(lines, data.get("high_profit_blocked", []))
        self._append_avoid_for_now(lines, data.get("low_profit_executable", []))
        self._append_operational_notes(lines)
        return "\n".join(lines)

    def _append_do_now(self, lines: list[str], rows: list[dict[str, Any]]) -> None:
        lines.append("## Do Now")
        lines.append("")
        lines.append("These are craftable with current account materials and profitable in the sampled market data.")
        lines.append("")
        for row in rows[:10]:
            lines.append(f"### {row.get('account_rank', row.get('rank'))}. {row.get('output_item_name', '')}")
            lines.append(f"- Net profit: `{coin(int(row.get('net_profit', 0)))}`")
            lines.append(f"- ROI: `{row.get('roi', 0)}`")
            lines.append(f"- Craft cost: `{coin(int(row.get('craft_cost', 0)))}`")
            lines.append(f"- Craftable now: `{row.get('account_feasibility', {}).get('craftable_now', 0)}`")
            lines.append(f"- Output item id: `{row.get('output_item_id', '')}`")
            self._append_explanation(lines, row)
            lines.append("")

    def _append_almost_ready(self, lines: list[str], rows: list[dict[str, Any]]) -> None:
        lines.append("## Almost Ready")
        lines.append("")
        lines.append("These are profitable and blocked by only a small number of missing ingredient counts. Verify Trading Post prices before buying missing materials.")
        lines.append("")
        for row in rows[:10]:
            lines.append(f"### {row.get('output_item_name', '')}")
            lines.append(f"- Net profit: `{coin(int(row.get('net_profit', 0)))}`")
            lines.append(f"- ROI: `{row.get('roi', 0)}`")
            lines.append(f"- Missing total count: `{row.get('account_feasibility', {}).get('missing_total_count', 0)}`")
            missing = self._compact_requirements(row, only_missing=True, limit=5)
            if missing:
                lines.append("- Missing:")
                for part in missing:
                    lines.append(f"  - {part}")
            self._append_explanation(lines, row)
            lines.append("")

    def _append_high_profit_blocked(self, lines: list[str], rows: list[dict[str, Any]]) -> None:
        lines.append("## High Profit But Blocked")
        lines.append("")
        lines.append("These have higher sampled profit but are not immediately craftable. Treat them as shopping-list candidates, not immediate actions.")
        lines.append("")
        for row in rows[:10]:
            missing = row.get("account_feasibility", {}).get("missing_total_count", 0)
            lines.append(f"- `{row.get('output_item_name', '')}`: profit `{coin(int(row.get('net_profit', 0)))}`, missing `{missing}`")
            self._append_explanation(lines, row, indent="  ")
        lines.append("")

    def _append_avoid_for_now(self, lines: list[str], rows: list[dict[str, Any]]) -> None:
        lines.append("## Avoid For Now")
        lines.append("")
        lines.append("These are craftable but not profitable in the current sample. They may still be useful for leveling crafting or account goals, but not for gold profit.")
        lines.append("")
        for row in rows[:10]:
            craftable = row.get("account_feasibility", {}).get("craftable_now", 0)
            lines.append(f"- `{row.get('output_item_name', '')}`: net `{coin(int(row.get('net_profit', 0)))}`, craftable `{craftable}`")
            self._append_explanation(lines, row, indent="  ")
        lines.append("")

    def _append_operational_notes(self, lines: list[str]) -> None:
        lines.append("## Operational Notes")
        lines.append("")
        lines.append("- This is based on a 250-recipe public sample, not full GW2 crafting coverage.")
        lines.append("- Trading Post prices move. Re-run prices/listings before taking large positions.")
        lines.append("- The report uses account snapshot materials, bank, character bags, and equipment to estimate current material availability.")
        lines.append("- For a beginner, prefer low-cost immediate crafts before high-profit blocked crafts.")

    def _compact_requirements(
        self,
        row: dict[str, Any],
        *,
        only_missing: bool = False,
        limit: int = 8,
    ) -> list[str]:
        requirements = row.get("account_feasibility", {}).get("requirements", [])
        if only_missing:
            requirements = [req for req in requirements if int(req.get("missing", 0)) > 0]
        parts = []
        for req in requirements[:limit]:
            parts.append(
                f"item {req.get('item_id')}: have {req.get('owned')}, need {req.get('required')}, missing {req.get('missing')}"
            )
        if len(requirements) > limit:
            parts.append(f"... +{len(requirements) - limit} more")
        return parts

    def _append_player_context(self, lines: list[str], data: dict[str, Any]) -> None:
        context = data.get("player_context", {})
        delta = context.get("snapshot_delta", {})
        lines.append("## Player Context")
        lines.append("")
        lines.append(f"- Goal: `{context.get('player_goal') or 'unspecified'}`")
        lines.append(f"- Account stage: `{context.get('account_stage') or 'unknown'}`")
        if delta:
            lines.append(f"- Snapshot delta: `{self._compact_delta(delta)}`")
        lines.append(f"- Explanation layer: `{context.get('llm_explanation_layer')}`")
        lines.append("")

    def _append_explanation(self, lines: list[str], row: dict[str, Any], *, indent: str = "") -> None:
        explanation = row.get("advice_explanation")
        if not explanation:
            return
        why = explanation.get("why_this_fits", [])
        risk = explanation.get("market_risk", {})
        if why:
            lines.append(f"{indent}- Why it fits: {'; '.join(why)}")
        risk_reasons = risk.get("reasons", [])
        if risk:
            reason_text = f" ({'; '.join(risk_reasons)})" if risk_reasons else ""
            lines.append(f"{indent}- Risk: `{risk.get('level', 'unknown')}`{reason_text}")
        expert_note = explanation.get("expert_note", "")
        if expert_note:
            lines.append(f"{indent}- Expert note: {expert_note}")

    def _include_explanations(self, data: dict[str, Any]) -> bool:
        return bool(data.get("player_context", {}).get("include_explanations"))

    def _rank_immediate(self, rows: Any) -> list[dict[str, Any]]:
        candidates = [
            row for row in self._as_rows(rows)
            if self._craftable_now(row) > 0 and self._int(row.get("net_profit")) > 0
        ]
        return sorted(candidates, key=self._immediate_key, reverse=True)

    def _rank_executable(self, rows: Any) -> list[dict[str, Any]]:
        candidates = [row for row in self._as_rows(rows) if self._craftable_now(row) > 0]
        return sorted(candidates, key=self._executable_key, reverse=True)

    def _rank_blocked(self, rows: Any) -> list[dict[str, Any]]:
        candidates = [row for row in self._as_rows(rows) if self._craftable_now(row) <= 0 and self._int(row.get("net_profit")) > 0]
        return sorted(candidates, key=lambda row: (self._missing_total(row), -self._int(row.get("net_profit")), -self._float(row.get("roi"))))

    def _immediate_key(self, row: dict[str, Any]) -> tuple[float, int, float, int]:
        return (
            self._float(row.get("account_executable_score", row.get("base_score", 0.0))),
            self._int(row.get("net_profit")),
            self._float(row.get("roi")),
            self._craftable_now(row),
        )

    def _executable_key(self, row: dict[str, Any]) -> tuple[int, float, int]:
        return (
            self._int(row.get("net_profit")),
            self._float(row.get("roi")),
            self._craftable_now(row),
        )

    def _as_rows(self, value: Any) -> list[dict[str, Any]]:
        return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []

    def _with_explanations(
        self,
        rows: list[dict[str, Any]],
        *,
        category: str,
        context: dict[str, Any],
        llm_budget: dict[str, int],
    ) -> list[dict[str, Any]]:
        if not context.get("include_explanations"):
            return rows
        enriched = []
        for row in rows:
            copy = dict(row)
            explanation = self._explain_row(copy, category=category, context=context)
            if self._use_llm_provider(context) and llm_budget["remaining"] > 0:
                explanation = self._with_llm_provider_explanation(copy, explanation, context=context)
                llm_budget["remaining"] -= 1
            copy["advice_explanation"] = explanation
            enriched.append(copy)
        return enriched

    def _explain_row(self, row: dict[str, Any], *, category: str, context: dict[str, Any]) -> dict[str, Any]:
        goal = str(context.get("player_goal", "")).lower()
        stage = str(context.get("account_stage", "")).lower()
        craftable = self._craftable_now(row)
        missing = self._missing_total(row)
        profit = self._int(row.get("net_profit"))
        craft_cost = self._int(row.get("craft_cost"))
        roi = self._float(row.get("roi"))
        why: list[str] = []

        if category == "do_now":
            why.append(f"current account materials can craft it {craftable} time(s)")
            why.append(f"sample net profit is {coin(profit)} with ROI {roi}")
            if "gold" in goal or "profit" in goal or "赚钱" in goal:
                why.append("it directly matches a gold/profit goal without extra shopping")
            if stage in {"beginner", "new_player", "early"} or "新手" in stage:
                why.append("low execution friction is suitable for an early account")
        elif category == "almost_ready":
            why.append(f"only {missing} missing ingredient count(s) block the craft")
            why.append(f"sample profit remains positive at {coin(profit)}")
            if "progress" in goal or "legendary" in goal or "collection" in goal:
                why.append("it is a practical shopping-list candidate for account progress")
        elif category == "high_profit_blocked":
            why.append(f"profit is high in the sample at {coin(profit)}")
            why.append(f"it is blocked by {missing} missing ingredient count(s), so it needs price verification first")
        else:
            why.append("current sample does not show positive gold profit")
            if "level" in goal or "练级" in goal:
                why.append("it may still be acceptable only if the goal is crafting progression")

        delta_note = self._delta_note(context.get("snapshot_delta", {}))
        if delta_note:
            why.append(delta_note)

        return {
            "category": category,
            "goal_fit": self._goal_fit(row, category=category, context=context),
            "why_this_fits": why,
            "market_risk": self._market_risk(row, context=context, category=category, craft_cost=craft_cost, profit=profit),
            "expert_note": "",
            "llm_provider": {"used": False, "mode": "not_requested"},
            "llm_prompt_facts": build_explanation_facts(
                {
                    "output_item_name": row.get("output_item_name", ""),
                    "output_item_id": row.get("output_item_id", ""),
                    "craftable_now": craftable,
                    "missing_total_count": missing,
                    "net_profit": profit,
                    "craft_cost": craft_cost,
                    "roi": roi,
                    "player_goal": context.get("player_goal", ""),
                    "account_stage": context.get("account_stage", ""),
                },
                self._market_risk(row, context=context, category=category, craft_cost=craft_cost, profit=profit),
                language=str(context.get("report_language", "en")),
            ),
        }

    def _with_llm_provider_explanation(
        self,
        row: dict[str, Any],
        explanation: dict[str, Any],
        *,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        layer = self._expert_layer(context)
        decision = {
            "decision": explanation.get("category", "review"),
            "reason": "Explain why this craft-vs-buy recommendation fits this specific GW2 account.",
            "factors": [
                {"name": "goal_fit", "value": 1 if explanation.get("goal_fit") == "strong" else 0.5, "weight": 2, "impact": "positive"},
                {"name": "net_profit", "value": explanation["llm_prompt_facts"].get("net_profit", 0), "weight": 1, "impact": "positive"},
                {"name": "market_risk", "value": 1 if explanation.get("market_risk", {}).get("level") == "high" else 0.2, "weight": 2, "impact": "negative"},
            ],
            "facts": explanation.get("llm_prompt_facts", {}),
            "constraints": [
                "Do not change item names, ids, categories, prices, risk levels, or numeric values.",
                "The final sentence must explicitly include these exact facts when present: output_item_name, craftable_now, net_profit_display, ROI value, and market_risk level.",
                "Use the exact ROI string from facts.roi and the exact profit string from facts.net_profit_display.",
                f"Return one concise {self._language_name(context)} player-facing sentence.",
                "Mention player goal, account stage, and risk only when supported by facts.",
                "If returning JSON, put the final sentence in content or guidance.",
            ],
        }
        provider_result = layer.explain_decision(
            decision,
            context={
                "player_context": self._safe_context_for_llm(context),
                "deterministic_explanation": {
                    "why_this_fits": explanation.get("why_this_fits", []),
                    "market_risk": explanation.get("market_risk", {}),
                },
                "output_item_name": row.get("output_item_name", ""),
            },
            use_provider=True,
        )
        enriched = dict(explanation)
        enriched["llm_provider"] = self._provider_metadata(provider_result)
        expert_note = self._provider_content(provider_result)
        if expert_note:
            validation = self._validate_provider_note(expert_note, enriched)
            enriched["llm_provider"]["validation"] = validation
            accepted_note = expert_note if validation["passed"] else self._deterministic_player_note(enriched)
            enriched["expert_note_source"] = "provider" if validation["passed"] else "codex_style_fallback"
            alignment = self._gold_standard_alignment(accepted_note, enriched)
            if not alignment["passed"]:
                accepted_note = self._deterministic_player_note(enriched)
                enriched["expert_note_source"] = "codex_style_fallback"
                alignment = self._gold_standard_alignment(accepted_note, enriched)
            enriched["expert_note"] = accepted_note
            enriched["gold_standard_alignment"] = alignment
        return enriched

    def _normalize_context(
        self,
        report: dict[str, Any],
        context: PlayerAdviceContext | dict[str, Any] | None,
    ) -> dict[str, Any]:
        raw: dict[str, Any]
        if isinstance(context, PlayerAdviceContext):
            raw = {
                "player_goal": context.player_goal,
                "account_stage": context.account_stage,
                "snapshot_delta": context.snapshot_delta or {},
                "market_risk": context.market_risk or {},
                "include_explanations": context.include_explanations,
                "report_language": context.report_language,
                "llm_explanation_layer": context.llm_explanation_layer,
                "llm_provider_key_file": context.llm_provider_key_file,
                "llm_provider_model": context.llm_provider_model,
                "llm_provider_limit": context.llm_provider_limit,
            }
        elif isinstance(context, dict):
            raw = dict(context)
        else:
            raw = {}

        return {
            "player_goal": str(raw.get("player_goal") or raw.get("goal") or ""),
            "account_stage": str(raw.get("account_stage") or self._infer_account_stage(report)),
            "snapshot_delta": raw.get("snapshot_delta") if isinstance(raw.get("snapshot_delta"), dict) else {},
            "market_risk": raw.get("market_risk") if isinstance(raw.get("market_risk"), dict) else {},
            "include_explanations": bool(raw.get("include_explanations", False)),
            "report_language": self._normalize_language(raw.get("report_language")),
            "llm_explanation_layer": str(raw.get("llm_explanation_layer") or "deterministic_template"),
            "_llm_provider_key_file": str(raw.get("llm_provider_key_file") or raw.get("_llm_provider_key_file") or ""),
            "llm_provider_model": str(raw.get("llm_provider_model") or ""),
            "llm_provider_limit": max(0, self._int(raw.get("llm_provider_limit"), default=3)),
        }

    def _use_llm_provider(self, context: dict[str, Any]) -> bool:
        layer = str(context.get("llm_explanation_layer", "")).lower()
        return layer in {"provider", "llm_provider", "openai_compatible", "real_provider"} or bool(context.get("use_llm_provider"))

    def _expert_layer(self, context: dict[str, Any]) -> LLMExpertLayer:
        if self.expert_layer is not None:
            return self.expert_layer
        key_file = str(context.get("_llm_provider_key_file") or "")
        config = LLMProviderConfig.from_env()
        if key_file:
            config = config.with_key_file(key_file)
        model = str(context.get("llm_provider_model") or "")
        if model:
            config = LLMProviderConfig(
                api_key=config.api_key,
                base_url=config.base_url,
                model=model,
                timeout_seconds=config.timeout_seconds,
                max_retries=config.max_retries,
                retry_backoff_seconds=config.retry_backoff_seconds,
            )
        return LLMExpertLayer(config=config)

    def _safe_context_for_llm(self, context: dict[str, Any]) -> dict[str, Any]:
        return {
            "player_goal": context.get("player_goal", ""),
            "account_stage": context.get("account_stage", ""),
            "snapshot_delta": context.get("snapshot_delta", {}),
            "market_risk": context.get("market_risk", {}),
            "report_language": context.get("report_language", "en"),
            "llm_explanation_layer": context.get("llm_explanation_layer", ""),
            "llm_provider_model": context.get("llm_provider_model", ""),
            "llm_provider_limit": context.get("llm_provider_limit", 0),
        }

    def _public_context(self, context: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in context.items() if not key.startswith("_")}

    def _provider_metadata(self, provider_result: dict[str, Any]) -> dict[str, Any]:
        config = provider_result.get("config", {})
        explanation = provider_result.get("explanation", {})
        error = provider_result.get("error") or {}
        return {
            "used": provider_result.get("provider") != "deterministic_expert",
            "provider": provider_result.get("provider", "unknown"),
            "mode": provider_result.get("mode", "unknown"),
            "model": config.get("model", ""),
            "configured": bool(config.get("configured", False)),
            "attempts": (explanation.get("attempts") if isinstance(explanation, dict) else None) or error.get("attempts"),
            "error": provider_result.get("error"),
        }

    def _provider_content(self, provider_result: dict[str, Any]) -> str:
        explanation = provider_result.get("explanation", {})
        if isinstance(explanation, dict):
            content = explanation.get("content") or explanation.get("summary") or ""
        else:
            content = str(explanation)
        content = self._extract_provider_guidance(content)
        return " ".join(str(content).strip().split())

    def _extract_provider_guidance(self, content: str) -> str:
        text = str(content).strip()
        if not text:
            return ""
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return text
        if isinstance(parsed, dict):
            for key in ("guidance", "content", "summary", "explanation"):
                value = parsed.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return text

    def _validate_provider_note(self, note: str, explanation: dict[str, Any]) -> dict[str, Any]:
        facts = explanation.get("llm_prompt_facts", {})
        risk = explanation.get("market_risk", {})
        return validate_explanation_candidate(
            note,
            facts,
            risk,
            category=str(explanation.get("category", "")),
            source="provider",
        ).to_dict()

    def _deterministic_player_note(self, explanation: dict[str, Any]) -> str:
        facts = explanation.get("llm_prompt_facts", {})
        risk = explanation.get("market_risk", {})
        item = facts.get("output_item_name", "this craft")
        craftable = self._int(facts.get("craftable_now"))
        profit = self._int(facts.get("net_profit"))
        roi = self._float(facts.get("roi"))
        risk_level = risk.get("level", "unknown")
        language = str(facts.get("report_language", "en")).lower()
        if language.startswith("zh"):
            return (
                f"{item} 适合先做小额尝试：当前材料可直接制作 {craftable} 次，"
                f"样本净利润 {coin(profit)}、ROI {roi}，市场风险为 {risk_level}；批量制作前仍需复查交易所价格。"
            )
        return (
            f"{item} is suitable for a small first craft: your current materials can craft it {craftable} time(s), "
            f"sample net profit is {coin(profit)} with ROI {roi}, and market risk is {risk_level}. "
            "Re-check Trading Post prices before scaling up."
        )

    def _gold_standard_alignment(self, note: str, explanation: dict[str, Any]) -> dict[str, Any]:
        facts = explanation.get("llm_prompt_facts", {})
        risk = explanation.get("market_risk", {})
        result = validate_explanation_candidate(
            note,
            facts,
            risk,
            category=str(explanation.get("category", "")),
            source=str(explanation.get("expert_note_source", "")),
        )
        checks = dict(result.checks)
        checks["final_note_not_invalid_provider_text"] = (
            bool(explanation.get("llm_provider", {}).get("validation", {}).get("passed", True))
            or explanation.get("expert_note_source") == "codex_style_fallback"
        )
        failed = [name for name, passed in checks.items() if not passed]
        return {
            "passed": not failed,
            "failed_checks": failed,
            "checks": checks,
            "policy": "new-input report is considered consistent with the Codex gold standard when facts, actionability, and risk boundaries are preserved",
            "constraint_layers": result.constraint_layers,
        }

    def _normalize_language(self, value: Any) -> str:
        return normalize_language(value)

    def _language_name(self, context: dict[str, Any]) -> str:
        return "Simplified Chinese" if str(context.get("report_language", "en")).startswith("zh") else "English"

    def _infer_account_stage(self, report: dict[str, Any]) -> str:
        holding = report.get("holding_summary", {})
        unique_items = self._int(holding.get("unique_item_ids"))
        total_count = self._int(holding.get("total_item_count"))
        if unique_items >= 1000 or total_count >= 50000:
            return "established"
        if unique_items >= 250 or total_count >= 10000:
            return "developing"
        if unique_items > 0 or total_count > 0:
            return "beginner"
        return "unknown"

    def _goal_fit(self, row: dict[str, Any], *, category: str, context: dict[str, Any]) -> str:
        goal = str(context.get("player_goal", "")).lower()
        if category == "do_now" and ("gold" in goal or "profit" in goal or "赚钱" in goal):
            return "strong"
        if category == "almost_ready" and self._missing_total(row) <= 2:
            return "medium"
        if category == "avoid" and ("level" in goal or "练级" in goal):
            return "conditional"
        if category == "avoid":
            return "weak"
        return "medium"

    def _market_risk(
        self,
        row: dict[str, Any],
        *,
        context: dict[str, Any],
        category: str,
        craft_cost: int,
        profit: int,
    ) -> dict[str, Any]:
        explicit = self._explicit_market_risk(row, context)
        if explicit:
            return explicit

        reasons: list[str] = []
        level = "low"
        if category in {"almost_ready", "high_profit_blocked"}:
            level = "medium"
            reasons.append("requires buying or waiting for missing materials")
        if craft_cost >= 100000:
            level = "high"
            reasons.append("large craft cost increases exposure to price movement")
        if profit <= 0:
            level = "high"
            reasons.append("sample net profit is not positive")
        if not reasons:
            reasons.append("immediate craft with positive sample profit")
        return {"level": level, "reasons": reasons}

    def _explicit_market_risk(self, row: dict[str, Any], context: dict[str, Any]) -> dict[str, Any] | None:
        risk = context.get("market_risk", {})
        output_item_id = str(row.get("output_item_id", ""))
        items = risk.get("items", {}) if isinstance(risk, dict) else {}
        value = items.get(output_item_id) if isinstance(items, dict) else None
        if value is None and isinstance(risk, dict):
            value = risk.get(output_item_id)
        if isinstance(value, str):
            return {"level": value, "reasons": ["provided by market risk input"]}
        if isinstance(value, dict):
            level = str(value.get("level") or value.get("risk") or "unknown")
            reasons = value.get("reasons") or value.get("reason") or []
            if isinstance(reasons, str):
                reasons = [reasons]
            return {"level": level, "reasons": [str(reason) for reason in reasons]}
        if isinstance(risk, dict) and isinstance(risk.get("default"), str):
            return {"level": str(risk["default"]), "reasons": ["default market risk input"]}
        return None

    def _delta_note(self, delta: Any) -> str:
        if not isinstance(delta, dict) or not delta:
            return ""
        gold_delta = self._int(delta.get("gold_delta_copper"), default=0)
        material_delta = self._int(delta.get("material_item_delta"), default=0)
        if gold_delta > 0 and material_delta >= 0:
            return f"recent snapshot delta shows {coin(gold_delta)} more liquid value and no material contraction signal"
        if material_delta > 0:
            return f"recent snapshot delta shows {material_delta} more material item count(s)"
        if gold_delta < 0:
            return f"recent snapshot delta shows {coin(gold_delta)} liquid value change, so avoid overcommitting"
        return ""

    def _compact_delta(self, delta: dict[str, Any]) -> str:
        parts = []
        for key in ("gold_delta_copper", "material_item_delta", "snapshot_count", "days_observed"):
            if key in delta:
                value = delta[key]
                if key == "gold_delta_copper":
                    value = coin(self._int(value))
                parts.append(f"{key}={value}")
        return ", ".join(parts) if parts else "provided"

    def _craftable_now(self, row: dict[str, Any]) -> int:
        return self._int(row.get("account_feasibility", {}).get("craftable_now", 0))

    def _missing_total(self, row: dict[str, Any]) -> int:
        return self._int(row.get("account_feasibility", {}).get("missing_total_count", 999))

    def _int(self, value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _float(self, value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
