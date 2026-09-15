"""Player behavior models — aggregates behavior rules into player-style profiles.

Used by the rule engine to produce typed behavior profiles (trader, crafter, etc.)
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any


class PlayerBehaviorProfile:
    """Aggregate behavior rules into a player-style profile."""

    def __init__(self, player_id: str) -> None:
        self.player_id = player_id
        self.action_counts: dict[str, int] = defaultdict(int)
        self.item_preferences: dict[str, int] = defaultdict(int)
        self.style_indicators: dict[str, float] = {}

    def record_action(self, action: dict[str, Any]) -> None:
        action_type = action.get("type", "unknown")
        self.action_counts[action_type] += 1
        item_id = action.get("item_id", "")
        if item_id:
            self.item_preferences[item_id] += 1

    def classify(self) -> str:
        total = sum(self.action_counts.values()) or 1
        trade_ratio = self.action_counts.get("trade", 0) / total
        craft_ratio = self.action_counts.get("craft", 0) / total
        farm_ratio = self.action_counts.get("farm", 0) / total
        flip_ratio = self.action_counts.get("flip", 0) / total

        if flip_ratio > 0.3:
            return "flipper"
        if trade_ratio > 0.4:
            return "trader"
        if craft_ratio > 0.3:
            return "crafter"
        if farm_ratio > 0.4:
            return "raider"
        return "collector"

    def to_dict(self) -> dict[str, Any]:
        return {
            "player_id": self.player_id,
            "style": self.classify(),
            "actions": dict(self.action_counts),
            "top_items": dict(sorted(self.item_preferences.items(), key=lambda x: -x[1])[:5]),
        }
