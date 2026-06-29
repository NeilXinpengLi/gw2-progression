from __future__ import annotations

from collections import Counter
from typing import Any


class PopulationIntelligence:
    """Population-level readout for behavior, strategy, and economy signals."""

    def summarize(self, engine: Any) -> dict[str, Any]:
        behavior_distribution = engine.behavior_model.population_distribution()
        strategy_adoption = self._strategy_adoption(engine)
        role_mix = self._role_mix(engine)
        economy_diffusion = self._economy_diffusion(engine)
        clusters = self._clusters(behavior_distribution, strategy_adoption, role_mix, economy_diffusion)

        return {
            "behavior_distribution": behavior_distribution,
            "role_mix": role_mix,
            "strategy_adoption": strategy_adoption,
            "economy_diffusion": economy_diffusion,
            "clusters": clusters,
            "signals": {
                "profiles": len(engine.behavior_model.profiles),
                "observations": len(engine.behavior_model.observations),
                "trajectory_length": engine.temporal.trajectory_length(),
                "agents": len(engine.agents),
            },
        }

    def _role_mix(self, engine: Any) -> dict[str, float]:
        counts = Counter(agent.profile.agent_type for agent in engine.agents.values())
        total = sum(counts.values())
        if total <= 0:
            return {}
        return {role: round(count / total, 4) for role, count in sorted(counts.items())}

    def _strategy_adoption(self, engine: Any) -> dict[str, Any]:
        actions: list[str] = []
        for snapshot in engine.temporal.history:
            action = snapshot.action or {}
            action_type = action.get("type")
            if action_type:
                actions.append(str(action_type))

        counts = Counter(actions)
        total = sum(counts.values())
        distribution = {
            action: round(count / total, 4)
            for action, count in sorted(counts.items())
        } if total else {}

        adoption_curve: list[dict[str, Any]] = []
        running = Counter()
        for snapshot in engine.temporal.history:
            action = snapshot.action or {}
            action_type = action.get("type")
            if not action_type:
                continue
            running[str(action_type)] += 1
            running_total = sum(running.values())
            adoption_curve.append({
                "t": snapshot.t,
                "dominant_strategy": running.most_common(1)[0][0],
                "share": round(running.most_common(1)[0][1] / running_total, 4),
            })

        return {
            "distribution": distribution,
            "dominant_strategy": max(distribution, key=distribution.get) if distribution else "unknown",
            "adoption_curve": adoption_curve[-20:],
        }

    def _economy_diffusion(self, engine: Any) -> dict[str, Any]:
        economy = engine.economy.to_dict()
        items = economy.get("items", {})
        if not items:
            return {
                "tracked_items": 0,
                "avg_volatility": 0.0,
                "market_phase": "unobserved",
                "top_diffusion_items": [],
            }

        volatilities = [float(item.get("volatility", 0.0)) for item in items.values()]
        avg_volatility = sum(volatilities) / max(len(volatilities), 1)
        ranked = sorted(
            (
                {
                    "item_id": item_id,
                    "diffusion_score": round(
                        float(item.get("demand", 0.0)) / max(float(item.get("supply", 1.0)), 0.01)
                        * (1.0 + float(item.get("volatility", 0.0))),
                        4,
                    ),
                }
                for item_id, item in items.items()
            ),
            key=lambda item: item["diffusion_score"],
            reverse=True,
        )

        if avg_volatility >= 0.25:
            market_phase = "volatile"
        elif engine.economy.market_health().get("market_sentiment", 0.5) >= 0.65:
            market_phase = "expansion"
        else:
            market_phase = "stable"

        return {
            "tracked_items": len(items),
            "avg_volatility": round(avg_volatility, 4),
            "market_phase": market_phase,
            "top_diffusion_items": ranked[:5],
        }

    def _clusters(
        self,
        behavior_distribution: dict[str, float],
        strategy_adoption: dict[str, Any],
        role_mix: dict[str, float],
        economy_diffusion: dict[str, Any],
    ) -> list[dict[str, Any]]:
        clusters: list[dict[str, Any]] = []
        for archetype, share in sorted(behavior_distribution.items(), key=lambda item: item[1], reverse=True):
            clusters.append({
                "cluster_id": f"behavior:{archetype}",
                "basis": "behavior",
                "label": archetype,
                "share": round(share, 4),
            })

        dominant_strategy = strategy_adoption.get("dominant_strategy", "unknown")
        if dominant_strategy != "unknown":
            clusters.append({
                "cluster_id": f"strategy:{dominant_strategy}",
                "basis": "strategy",
                "label": dominant_strategy,
                "share": strategy_adoption.get("distribution", {}).get(dominant_strategy, 0.0),
            })

        for role, share in sorted(role_mix.items(), key=lambda item: item[1], reverse=True)[:3]:
            clusters.append({
                "cluster_id": f"role:{role}",
                "basis": "agent_role",
                "label": role,
                "share": share,
            })

        clusters.append({
            "cluster_id": f"market:{economy_diffusion.get('market_phase', 'unobserved')}",
            "basis": "economy",
            "label": economy_diffusion.get("market_phase", "unobserved"),
            "share": 1.0 if economy_diffusion.get("tracked_items", 0) else 0.0,
        })
        return clusters
