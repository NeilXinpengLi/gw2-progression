"""Ontology-backed constraints for player-facing explanation text.

The advice layer may use an LLM provider to draft prose, but ontology facts
remain authoritative. This module makes those constraints reusable by QA,
policy, report generation, and future semantic graph ingestion.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

ONTOLOGY_EXPLANATION_CONSTRAINTS: dict[str, Any] = {
    "entity_layer": {
        "authoritative_facts": [
            "output_item_name",
            "output_item_id",
            "craftable_now",
            "missing_total_count",
            "net_profit_display",
            "craft_cost_display",
            "roi",
            "market_risk.level",
        ],
        "rule": "Explanation text must preserve all authoritative facts used by the recommendation.",
    },
    "relation_layer": {
        "relations": [
            "recommendation explains player_goal",
            "recommendation applies_to account_stage",
            "recommendation references market_risk",
            "recommendation derived_from craft_feasibility",
        ],
        "rule": "Explanation text must not contradict recommendation-to-fact relations.",
    },
    "action_layer": {
        "boundaries": [
            "craft now only when craftable_now > 0 and net_profit > 0",
            "blocked crafts must not be described as immediately executable",
            "low-profit crafts must not be framed as gold-profit actions",
            "large scale actions must include price re-check guidance",
        ],
        "rule": "Explanation text must preserve the action boundary implied by the recommendation category.",
    },
    "governance_layer": {
        "publish_gate": [
            "fact_preservation",
            "risk_disclosure",
            "actionability",
            "no_private_or_key_leak",
            "language_policy",
        ],
        "rule": "Provider text may be published only when all blocking constraints pass.",
    },
}


@dataclass(frozen=True)
class ExplanationConstraintResult:
    passed: bool
    violations: list[str]
    checks: dict[str, bool]
    constraint_layers: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "violations": self.violations,
            "checks": self.checks,
            "constraint_layers": self.constraint_layers,
        }


def coin_display(copper: int) -> str:
    sign = "-" if copper < 0 else ""
    copper = abs(int(copper))
    gold, rem = divmod(copper, 10000)
    silver, copper = divmod(rem, 100)
    if gold:
        return f"{sign}{gold}g {silver}s {copper}c"
    if silver:
        return f"{sign}{silver}s {copper}c"
    return f"{sign}{copper}c"


def build_explanation_facts(raw_facts: dict[str, Any], risk: dict[str, Any], *, language: str = "en") -> dict[str, Any]:
    net_profit = _int(raw_facts.get("net_profit"))
    craft_cost = _int(raw_facts.get("craft_cost"))
    facts = dict(raw_facts)
    facts["net_profit_display"] = raw_facts.get("net_profit_display") or coin_display(net_profit)
    facts["craft_cost_display"] = raw_facts.get("craft_cost_display") or coin_display(craft_cost)
    facts["risk_level"] = str(risk.get("level", "")).lower()
    facts["report_language"] = normalize_language(language)
    return facts


def validate_explanation_candidate(
    note: str,
    facts: dict[str, Any],
    risk: dict[str, Any],
    *,
    category: str = "",
    source: str = "provider",
) -> ExplanationConstraintResult:
    text = str(note or "")
    lower = text.lower()
    normalized_language = normalize_language(facts.get("report_language"))
    risk_level = str(risk.get("level", facts.get("risk_level", ""))).lower()
    missing = _int(facts.get("missing_total_count"))
    craftable = _int(facts.get("craftable_now"))
    profit = _int(facts.get("net_profit"))
    roi = _float(facts.get("roi"))
    item_name = str(facts.get("output_item_name", ""))
    net_profit_display = str(facts.get("net_profit_display") or coin_display(profit))

    checks = {
        "item_preserved": bool(item_name and item_name in text),
        "craftable_preserved": str(craftable) in text,
        "profit_preserved": net_profit_display in text or str(profit) in text,
        "roi_preserved": str(roi) in text,
        "risk_preserved": _risk_in_text(risk_level, text, lower),
        "actionable": _actionable(text, lower),
        "language_policy": _language_ok(normalized_language, text),
        "no_profit_currency_scale_error": not _profit_currency_scale_error(text, lower, profit, net_profit_display),
        "no_missing_material_contradiction": not (missing == 0 and _mentions_missing(text, lower)),
        "no_risk_level_contradiction": not (risk_level == "low" and ("高风险" in text or "high risk" in lower)),
        "category_action_boundary": _category_boundary_ok(category, craftable, profit, lower),
        "no_overconfident_scale_up": "大量" not in text and "mass craft" not in lower and "大量制作" not in text,
    }
    violations = [name for name, passed in checks.items() if not passed]
    return ExplanationConstraintResult(
        passed=not violations,
        violations=violations,
        checks=checks,
        constraint_layers=ONTOLOGY_EXPLANATION_CONSTRAINTS,
    )


def normalize_language(value: Any) -> str:
    language = str(value or "en").strip().lower()
    return "zh" if language in {"zh", "cn", "chinese", "zh-cn", "中文"} else "en"


def _risk_in_text(risk_level: str, text: str, lower: str) -> bool:
    if not risk_level:
        return True
    return risk_level in lower or (risk_level == "low" and "低风险" in text)


def _actionable(text: str, lower: str) -> bool:
    return any(token in lower for token in ("craft", "try", "check", "re-check", "review", "scale")) or any(
        token in text for token in ("制作", "尝试", "复查", "执行", "建议")
    )


def _language_ok(language: str, text: str) -> bool:
    has_cjk = any("\u4e00" <= ch <= "\u9fff" for ch in text)
    return has_cjk if language == "zh" else not has_cjk


def _profit_currency_scale_error(text: str, lower: str, profit: int, net_profit_display: str) -> bool:
    if profit >= 10000:
        return False
    return ("金" in text or "gold" in lower or "g " in lower) and net_profit_display not in text and str(profit) not in text


def _mentions_missing(text: str, lower: str) -> bool:
    return "缺" in text or "missing" in lower or "short of" in lower


def _category_boundary_ok(category: str, craftable: int, profit: int, lower: str) -> bool:
    if category == "do_now":
        return craftable > 0 and profit > 0
    if category == "avoid":
        return "gold profit" not in lower or profit > 0
    if category in {"almost_ready", "high_profit_blocked"}:
        return "immediately craft" not in lower and "craft now" not in lower
    return True


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
