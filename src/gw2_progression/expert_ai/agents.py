"""Multi-agent orchestration for GW2 Expert AI."""

from __future__ import annotations

from typing import Any


class EconomyAgent:
    def __init__(self, simulator: Any, data_source: Any) -> None:
        self.simulator = simulator
        self.data_source = data_source

    def run(self, task: dict[str, Any]) -> dict[str, Any]:
        market = self.data_source.fetch_items(task.get("item_ids"))
        items = task.get("items") or market["items"]
        return {"agent": "EconomyAgent", "market": market, "simulation": self.simulator.simulate(items)}


class MetaAgent:
    def __init__(self, engine: Any, data_source: Any) -> None:
        self.engine = engine
        self.data_source = data_source

    def run(self, task: dict[str, Any]) -> dict[str, Any]:
        builds = self.data_source.fetch_builds(task.get("profession"))
        build = task.get("build") or (builds["builds"][0] if builds["builds"] else {})
        return {"agent": "MetaAgent", "meta_source": builds, "analysis": self.engine.analyze_build(build)}


class BuildAgent:
    def run(self, task: dict[str, Any]) -> dict[str, Any]:
        build = task.get("build", {})
        missing = build.get("missing_items", [])
        completion = float(build.get("gear_completion_percent", 0))
        return {"agent": "BuildAgent", "missing_items": missing, "completion": completion, "ready": completion >= 90 and not missing}


class PlannerAgent:
    def __init__(self, planner: Any) -> None:
        self.planner = planner

    def run(self, task: dict[str, Any]) -> dict[str, Any]:
        return {"agent": "PlannerAgent", **self.planner.generate(task.get("goals", []), task.get("constraints", {}))}


class AgentOrchestrator:
    """Coordinate economy, meta, build, and planner agent outputs."""

    def __init__(self, system: Any, economy_source: Any, meta_source: Any) -> None:
        self.system = system
        self.economy = EconomyAgent(system.economy, economy_source)
        self.meta = MetaAgent(system.meta, meta_source)
        self.build = BuildAgent()
        self.planner = PlannerAgent(system.planner)

    def run(self, task: dict[str, Any]) -> dict[str, Any]:
        outputs = [
            self.economy.run(task),
            self.meta.run(task),
            self.build.run(task),
            self.planner.run(task),
        ]
        risk = self._risk(outputs)
        decision = self.system.evaluate_decision({
            "decision_type": "approve_recommendation",
            "factors": [
                {"name": "agent_alignment", "value": self._alignment(outputs), "weight": 0.7, "impact": "positive"},
                {"name": "orchestration_risk", "value": risk, "weight": 0.3, "impact": "negative" if risk >= 0.7 else "positive"},
            ],
        })
        return {"outputs": outputs, "coordination": {"risk": risk, "decision": decision}}

    def _alignment(self, outputs: list[dict[str, Any]]) -> float:
        ready_signals = 0
        ready_signals += 1 if outputs[0]["simulation"].get("market_risk") == "LOW" else 0
        ready_signals += 1 if outputs[1]["analysis"].get("raid_viability") in {"ready", "review"} else 0
        ready_signals += 1 if outputs[2].get("ready") else 0
        ready_signals += 1 if outputs[3].get("plan") else 0
        return ready_signals / 4

    def _risk(self, outputs: list[dict[str, Any]]) -> float:
        risk = 0.0
        risk += 0.35 if outputs[0]["simulation"].get("market_risk") == "HIGH" else 0.05
        risk += 0.25 if outputs[1]["analysis"].get("raid_viability") == "not_ready" else 0.05
        risk += 0.2 if not outputs[2].get("ready") else 0.0
        risk += 0.2 if any(step.get("decision") != "APPROVE" for step in outputs[3].get("plan", [])) else 0.0
        return round(min(risk, 1.0), 3)
