from __future__ import annotations

from copy import deepcopy
from typing import Any

from gw2_progression.lifecycle.core.backward.dependency_solver import DependencySolver


class StateEvolver:
    def __init__(self, step_size: int = 1, solver: DependencySolver | None = None) -> None:
        self.step_size = step_size
        self.solver = solver or DependencySolver()

    def evolve(self, state: dict[str, Any], action: dict[str, Any]) -> dict[str, Any]:
        new_state = deepcopy(state)
        action_type = action.get("type", "skip")
        item_id = action.get("item_id")
        quantity = int(action.get("quantity", 1))
        inventory = new_state.setdefault("inventory", {})
        market = new_state.setdefault("market", {})
        validations = new_state.setdefault("_action_validations", [])

        if action_type in ("farm", "collect", "gather"):
            inventory[item_id] = inventory.get(item_id, 0) + quantity
            if item_id in market:
                market[item_id]["supply"] = market[item_id].get("supply", 100) + quantity
            validations.append({
                "action": action_type,
                "item_id": item_id,
                "valid": True,
                "reason": f"gained {quantity}x {item_id}",
            })

        elif action_type == "trade":
            inventory[item_id] = inventory.get(item_id, 0) + quantity
            if item_id in market:
                market[item_id]["demand"] = market[item_id].get("demand", 100) + quantity
            validations.append({
                "action": "trade",
                "item_id": item_id,
                "valid": True,
                "reason": f"traded {quantity}x {item_id}",
            })

        elif action_type == "craft":
            consumes = action.get("consumes", {})
            recipe_sourced = action.get("recipe_sourced", False)
            all_present = True
            missing: list[str] = []
            for consumed, cqty in consumes.items():
                have = inventory.get(consumed, 0)
                need = int(cqty)
                if have < need:
                    all_present = False
                    missing.append(f"{consumed} (have {have}, need {need})")
            if recipe_sourced and all_present:
                for consumed, cqty in consumes.items():
                    inventory[consumed] = max(inventory.get(consumed, 0) - int(cqty), 0)
                produced_qty = action.get("produced_quantity", 1)
                inventory[item_id] = inventory.get(item_id, 0) + produced_qty
                if item_id in market:
                    market[item_id]["supply"] = market[item_id].get("supply", 100) + produced_qty
                validations.append({
                    "action": "craft",
                    "item_id": item_id,
                    "valid": True,
                    "recipe_sourced": True,
                    "reason": f"crafted {produced_qty}x {item_id} from {len(consumes)} ingredients",
                })
            elif recipe_sourced and not all_present:
                validations.append({
                    "action": "craft",
                    "item_id": item_id,
                    "valid": False,
                    "recipe_sourced": True,
                    "reason": f"missing ingredients: {'; '.join(missing)}",
                    "missing": missing,
                })
            else:
                for consumed, cqty in consumes.items():
                    inventory[consumed] = max(inventory.get(consumed, 0) - int(cqty), 0)
                inventory[item_id] = inventory.get(item_id, 0) + 1
                if item_id in market:
                    market[item_id]["supply"] = market[item_id].get("supply", 100) + 1
                validations.append({
                    "action": "craft",
                    "item_id": item_id,
                    "valid": True,
                    "recipe_sourced": False,
                    "reason": f"non-recipe craft {item_id}",
                })

        elif action_type == "achievement":
            achievements = new_state.setdefault("achievements", [])
            if item_id and item_id not in achievements:
                achievements.append(item_id)
            validations.append({
                "action": "achievement",
                "item_id": item_id,
                "valid": True,
                "reason": f"completed achievement {item_id}",
            })

        new_state["time"] = new_state.get("time", 0) + self.step_size
        return new_state

    def evolve_multi(self, state: dict[str, Any], actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        trajectory = [deepcopy(state)]
        current = deepcopy(state)
        for action in actions:
            current = self.evolve(current, action)
            trajectory.append(deepcopy(current))
        return trajectory

    def validation_summary(self, state: dict[str, Any]) -> dict[str, Any]:
        validations = state.get("_action_validations", [])
        total = len(validations)
        valid = sum(1 for v in validations if v.get("valid"))
        invalid = total - valid
        recipe_crafts = [v for v in validations if v.get("action") == "craft" and v.get("recipe_sourced")]
        valid_recipe = sum(1 for v in recipe_crafts if v.get("valid"))
        return {
            "total_actions": total,
            "valid": valid,
            "invalid": invalid,
            "recipe_crafts": len(recipe_crafts),
            "valid_recipe_crafts": valid_recipe,
            "invalid_recipe_crafts": len(recipe_crafts) - valid_recipe,
            "accuracy": round(valid / max(total, 1), 4),
            "recipe_accuracy": round(valid_recipe / max(len(recipe_crafts), 1), 4),
        }
