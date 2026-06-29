"""GW2 Rule Engine v1 — unified rule extraction, learning, mining, distillation, and validation.

This is the core convergence layer that wraps:
  - API structural rule extraction  (APIRuleExtractor)
  - Economy rule learning           (EconomyRuleLearner)
  - Behavior rule mining            (BehaviorRuleMiner)
  - LLM rule distillation           (LLMRuleDistiller)
  - Simulation-driven validation    (SimulationValidator)

Architecture aligns with the spec's core/engine.py -> GW2RuleEngine.
"""

from __future__ import annotations

from typing import Any

from gw2_progression.expert_ai.simulation import SyntheticSimulationEngine
from gw2_progression.rule_engine.core.api_rules.extractor import APIRuleExtractor
from gw2_progression.rule_engine.core.api_rules.graph_builder import RuleGraphBuilder
from gw2_progression.rule_engine.core.api_rules.schema_parser import Rule
from gw2_progression.rule_engine.core.behavior_rules.pattern_miner import BehaviorRuleMiner
from gw2_progression.rule_engine.core.economy_rules.price_model import EconomyRuleLearner
from gw2_progression.rule_engine.core.economy_rules.trend_inference import TrendInference
from gw2_progression.rule_engine.core.llm_rules.distiller import LLMRuleDistiller
from gw2_progression.rule_engine.core.llm_rules.reasoning_converter import ReasoningConverter
from gw2_progression.rule_engine.core.validation.rule_checker import RuleChecker
from gw2_progression.rule_engine.core.validation.simulation_runner import SimulationValidator


class GW2RuleEngine:
    """Unified Rule Engine — the core facade.

    Maps to the spec's core/engine.py:
      self.api      = APIRuleExtractor()
      self.economy  = EconomyRuleLearner()
      self.behavior = BehaviorRuleMiner()
      self.llm      = LLMRuleDistiller()
      self.validator = SimulationValidator()

    Usage:
      engine = GW2RuleEngine()
      result = engine.run(data={
          "api": [...], "prices": {...}, "logs": [...], "world": {...}
      })
    """

    def __init__(self, llm_layer: Any | None = None, simulation: SyntheticSimulationEngine | None = None) -> None:
        self.api = APIRuleExtractor()
        self.economy = EconomyRuleLearner()
        self.behavior = BehaviorRuleMiner()
        self.llm = LLMRuleDistiller(llm_layer=llm_layer)
        self.validator = SimulationValidator(simulation_engine=simulation)
        self.graph_builder = RuleGraphBuilder()
        self.trends = TrendInference()
        self.checker = RuleChecker()
        self.converter = ReasoningConverter()

    def run(self, data: dict[str, Any]) -> dict[str, Any]:
        """Full rule engine pipeline: extract → learn → mine → distill → validate.

        spec's engine.run():
          api_rules  = self.api.extract(data["api"])
          eco_rules  = self.economy.learn(data["prices"])
          beh_rules  = self.behavior.mine(data["logs"])
          raw_rules  = api_rules + eco_rules + beh_rules
          llm_rules  = self.llm.distill(raw_rules)
          validated  = self.validator.validate(llm_rules, data["world"])
        """
        api_rules = self.api.extract(data.get("api"))
        eco_result = self.economy.learn(data.get("prices"))
        eco_rules = []
        for cat in ("trend", "elasticity", "shock_response"):
            eco_rules.extend(eco_result.get(cat, []))
        beh_result = self.behavior.mine(data.get("logs", []))
        beh_rules = []
        for cat in ("farming_loops", "trading_behaviors", "meta_adaptations"):
            beh_rules.extend(beh_result.get(cat, []))

        raw_rules = api_rules + eco_rules + beh_rules

        reasoning_rules = []
        if "reasoning" in data:
            reasoning_rules = self.converter.convert(data["reasoning"])
            raw_rules.extend(reasoning_rules)

        llm_rules = self.llm.distill(raw_rules)

        graph = self.graph_builder.build(llm_rules)
        validated = self.validator.validate(llm_rules, data.get("world", {}))

        economy_trends = self.trends.infer([r.to_dict() for r in eco_rules])
        rule_check = self.checker.check(llm_rules)

        return {
            "rule_count": len(llm_rules),
            "raw_count": {"api": len(api_rules), "economy": len(eco_rules), "behavior": len(beh_rules), "reasoning": len(reasoning_rules)},
            "api_rules": [r.to_dict() for r in api_rules],
            "economy_rules": [r.to_dict() for r in eco_rules],
            "behavior_rules": [r.to_dict() for r in beh_rules],
            "reasoning_rules": [r.to_dict() for r in reasoning_rules],
            "llm_distilled": [r.to_dict() for r in llm_rules],
            "validated": validated,
            "graph": {"nodes": list(graph.nodes.keys()), "edges": graph.edges},
            "economy_trends": economy_trends,
            "rule_check": rule_check,
            "engine_version": "v1.0",
        }

    def extract_api(self, schemas: list | None = None) -> dict[str, Any]:
        return self.api.extract_all()

    def learn_economy(self, price_series: dict | None = None) -> list[dict[str, Any]]:
        return [r.to_dict() for r in self.economy.learn_as_rules(price_series)]

    def mine_behavior(self, logs: list[dict] | None = None) -> list[dict[str, Any]]:
        return [r.to_dict() for r in self.behavior.mine_as_rules(logs or [])]

    def distill(self, rules: list[Rule] | None = None) -> list[dict[str, Any]]:
        return [r.to_dict() for r in self.llm.distill(rules or [])]

    def validate(self, rules: list[Rule] | None = None, world: dict | None = None) -> list[dict[str, Any]]:
        return self.validator.validate(rules or [], world or {})

    def check(self, rules: list[Rule]) -> dict[str, Any]:
        return self.checker.check(rules)
