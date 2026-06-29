"""Behavior Rule Miner — mines player behavior patterns from interaction logs.

Wraps the existing SyntheticSimulationEngine + agent system to extract
behavioral rules: farming cycles, trading strategies, meta adaptation.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from gw2_progression.rule_engine.core.api_rules.schema_parser import Rule, RuleType


class BehaviorRuleMiner:
    """Mines structured behavior rules from player action logs."""

    def mine(self, player_logs: list[dict[str, Any]]) -> dict[str, Any]:
        patterns: dict[str, Any] = {}

        patterns["farming_loops"] = self.detect_farming_loop(player_logs)
        patterns["trading_behaviors"] = self.detect_trading_behavior(player_logs)
        patterns["meta_adaptations"] = self.detect_meta_adaptation(player_logs)

        return patterns

    def detect_farming_loop(self, logs: list[dict[str, Any]]) -> list[Rule]:
        rules: list[Rule] = []
        action_sequences: list[tuple[str, ...]] = []
        current: list[str] = []
        for entry in logs:
            action = entry.get("action", {}).get("type", "")
            if action:
                current.append(action)
            if entry.get("world_time", 0) % 5 == 0 and current:
                if len(current) >= 2:
                    action_sequences.append(tuple(current))
                current = []

        if action_sequences:
            common = Counter(action_sequences).most_common(3)
            for seq, count in common:
                rules.append(Rule(
                    id=f"farming_loop_{'_'.join(seq[:3])}",
                    type=RuleType.BEHAVIOR_PATTERN,
                    source="player_logs",
                    condition={"sequence": list(seq), "frequency": count},
                    action="predict_next_action",
                    confidence=min(0.9, count / max(len(action_sequences), 1) * 2),
                    metadata={"sequence": list(seq), "occurrences": count},
                ))
        return rules

    def detect_trading_behavior(self, logs: list[dict[str, Any]]) -> list[Rule]:
        rules: list[Rule] = []
        style_groups = defaultdict(list)
        for entry in logs:
            action = entry.get("action", {})
            action_type = action.get("type", "")
            if action_type in ("trade", "flip"):
                item_id = action.get("item_id", "unknown")
                price = action.get("price", 0)
                style = entry.get("player_id", "").split(":")[0] if ":" in entry.get("player_id", "") else entry.get("player_id", "")
                style_groups[style].append({"item_id": item_id, "price": price, "action": action_type})

        for style, trades in style_groups.items():
            if len(trades) >= 3:
                avg_price = sum(t["price"] for t in trades) / len(trades)
                buy_count = sum(1 for t in trades if t["action"] == "trade")
                flip_count = sum(1 for t in trades if t["action"] == "flip")
                rules.append(Rule(
                    id=f"trading_{style}",
                    type=RuleType.BEHAVIOR_PATTERN,
                    source="player_logs",
                    condition={"style": style, "avg_price": round(avg_price, 2), "trade_ratio": round(buy_count / max(flip_count, 1), 2)},
                    action=f"optimize_{style}_trades",
                    confidence=min(0.85, len(trades) * 0.05),
                    metadata={"style": style, "total_trades": len(trades), "buy_count": buy_count, "flip_count": flip_count},
                ))
        return rules

    def detect_meta_adaptation(self, logs: list[dict[str, Any]]) -> list[Rule]:
        rules: list[Rule] = []
        farm_types = set()
        for entry in logs:
            action = entry.get("action", {})
            if action.get("type") == "farm":
                farm_types.add(action.get("item_id", ""))

        if farm_types:
            rules.append(Rule(
                id="meta_adaptation",
                type=RuleType.BEHAVIOR_PATTERN,
                source="player_logs",
                condition={"farmed_items": list(farm_types), "diversity": len(farm_types)},
                action="recommend_farm_rotation" if len(farm_types) > 1 else "deepen_single_farm",
                confidence=min(0.8, len(farm_types) * 0.15),
                metadata={"farmed_count": len(farm_types), "items": list(farm_types)},
            ))
        return rules

    def mine_as_rules(self, player_logs: list[dict[str, Any]]) -> list[Rule]:
        result = self.mine(player_logs)
        all_rules: list[Rule] = []
        for category in ("farming_loops", "trading_behaviors", "meta_adaptations"):
            all_rules.extend(result.get(category, []))
        return all_rules
