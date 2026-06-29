"""LLM Rule Distiller — uses LLM to abstract raw rules into GW2 expert reasoning logic.

Wraps the existing LLMExpertLayer to produce higher-level meta reasoning rules.
"""

from __future__ import annotations

from typing import Any

from gw2_progression.rule_engine.core.api_rules.schema_parser import Rule, RuleType


class LLMRuleDistiller:
    """Distills extracted rules into higher-level GW2 expert reasoning via LLM.

    Uses the existing LLMExpertLayer (OpenAI-compatible) when configured,
    falls back to deterministic pattern-based distillation.
    """

    def __init__(self, llm_layer: Any | None = None) -> None:
        self._llm = llm_layer
        self._use_llm = False
        if llm_layer:
            try:
                cfg = llm_layer.provider_config
                self._use_llm = bool(cfg and cfg.api_key and cfg.base_url)
            except Exception:
                pass

    def distill(self, rules: list[Rule]) -> list[Rule]:
        if self._use_llm and self._llm:
            return self._distill_via_llm(rules)
        return self._distill_deterministic(rules)

    def _distill_deterministic(self, rules: list[Rule]) -> list[Rule]:
        distilled: list[Rule] = []
        grouped: dict[str, list[Rule]] = {}
        for r in rules:
            key = r.type.value
            grouped.setdefault(key, []).append(r)

        for rtype, group in grouped.items():
            avg_conf = sum(r.confidence for r in group) / max(len(group), 1)
            sources = list({r.source for r in group})
            distilled.append(Rule(
                id=f"meta_{rtype}",
                type=RuleType.LLM_DISTILLED,
                source=f"distilled:{rtype}",
                condition={
                    "source_rules": len(group),
                    "aggregated_from": sources[:20],
                    "avg_confidence": round(avg_conf, 3),
                },
                action=f"apply_{rtype}_rules",
                confidence=min(0.95, avg_conf + 0.1),
                metadata={
                    "rule_type": rtype,
                    "rule_count": len(group),
                    "sources": sources[:50],
                    "distillation_method": "deterministic_aggregation",
                },
            ))
        return distilled

    def _distill_via_llm(self, rules: list[Rule]) -> list[Rule]:
        prompt = self._build_prompt(rules)
        try:
            llm_output = self._llm.think({"prompt": prompt, "context": "rule_distillation"})
            raw_rules = llm_output.get("reasoning", llm_output.get("response", ""))
            parsed = self._parse_llm_rules(raw_rules, rules)
            return parsed if parsed else self._distill_deterministic(rules)
        except Exception:
            return self._distill_deterministic(rules)

    def _build_prompt(self, rules: list[Rule]) -> str:
        rule_summary = "\n".join(f"  [{r.type.value}] {r.source}: {r.condition} -> {r.action} (conf={r.confidence})" for r in rules[:30])
        return (
            f"You are a GW2 expert system. Analyze these {len(rules)} extracted game rules "
            f"and distill them into higher-level GW2 expert reasoning patterns.\n\n"
            f"Raw Rules:\n{rule_summary}\n\n"
            f"Output format:\n"
            f"- pattern: <name>\n"
            f"- reasoning: <GW2 expert logic>\n"
            f"- confidence: <0-1>\n"
        )

    def _parse_llm_rules(self, raw: Any, original: list[Rule]) -> list[Rule]:
        if isinstance(raw, list):
            return [Rule.from_dict(r) if isinstance(r, dict) else r for r in raw if isinstance(r, (dict, Rule))]
        return []

    def distill_as_rules(self, rules: list[Rule]) -> list[Rule]:
        return self.distill(rules)
