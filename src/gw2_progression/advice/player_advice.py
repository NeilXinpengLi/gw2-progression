from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


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


class PlayerAdviceEngine:
    """Converts account-aware craft feasibility data into player-facing advice."""

    def from_file(self, feasibility_report_path: str | Path) -> PlayerAdviceResult:
        path = Path(feasibility_report_path)
        report = json.loads(path.read_text(encoding="utf-8"))
        return self.from_report(report, source_report=str(path))

    def from_report(self, report: dict[str, Any], source_report: str = "") -> PlayerAdviceResult:
        run_id = str(report.get("run_id", "unknown"))
        account_name = str(report.get("account_name", "unknown"))
        immediate = list(report.get("top_executable_profitable", []))
        executable = list(report.get("top_executable", []))
        blocked = list(report.get("blocked_profitable_lowest_missing", []))

        low_profit_executable = [row for row in executable if int(row.get("net_profit", 0)) <= 0][:10]
        near_blocked = [
            row
            for row in blocked
            if int(row.get("account_feasibility", {}).get("missing_total_count", 999)) <= 3
        ][:15]
        high_profit_blocked = sorted(
            [row for row in blocked if int(row.get("net_profit", 0)) > 500],
            key=lambda row: int(row.get("net_profit", 0)),
            reverse=True,
        )[:10]

        data = {
            "source_report": source_report,
            "account_name": account_name,
            "holding_summary": report.get("holding_summary", {}),
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
            lines.append("")

    def _append_high_profit_blocked(self, lines: list[str], rows: list[dict[str, Any]]) -> None:
        lines.append("## High Profit But Blocked")
        lines.append("")
        lines.append("These have higher sampled profit but are not immediately craftable. Treat them as shopping-list candidates, not immediate actions.")
        lines.append("")
        for row in rows[:10]:
            missing = row.get("account_feasibility", {}).get("missing_total_count", 0)
            lines.append(f"- `{row.get('output_item_name', '')}`: profit `{coin(int(row.get('net_profit', 0)))}`, missing `{missing}`")
        lines.append("")

    def _append_avoid_for_now(self, lines: list[str], rows: list[dict[str, Any]]) -> None:
        lines.append("## Avoid For Now")
        lines.append("")
        lines.append("These are craftable but not profitable in the current sample. They may still be useful for leveling crafting or account goals, but not for gold profit.")
        lines.append("")
        for row in rows[:10]:
            craftable = row.get("account_feasibility", {}).get("craftable_now", 0)
            lines.append(f"- `{row.get('output_item_name', '')}`: net `{coin(int(row.get('net_profit', 0)))}`, craftable `{craftable}`")
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
