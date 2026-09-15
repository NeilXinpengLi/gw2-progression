from __future__ import annotations

from typing import Any


class ConsistencyChecker:
    def __init__(self, tolerance: float = 0.15) -> None:
        self.tolerance = tolerance

    def validate(self, reconstructed: dict[str, Any], final_state: dict[str, Any]) -> bool:
        if not reconstructed or not final_state:
            return False
        return self.match_ratio(reconstructed, final_state) >= (1.0 - self.tolerance)

    def match_ratio(self, reconstructed: dict[str, Any], final_state: dict[str, Any]) -> float:
        matches = 0
        total = 0
        for key in ("inventory", "market", "achievements", "gold", "equipment"):
            r_val = reconstructed.get(key)
            f_val = final_state.get(key)
            if r_val is not None and f_val is not None:
                total += 1
                if self._dicts_match(r_val, f_val) if isinstance(r_val, dict) else r_val == f_val:
                    matches += 1
                elif isinstance(r_val, list) and isinstance(f_val, list):
                    if self._lists_match(r_val, f_val):
                        matches += 1
        return matches / max(total, 1)

    def validate_trajectory(self, trajectory: list[dict[str, Any]], final_state: dict[str, Any]) -> float:
        if not trajectory:
            return 0.0
        end_state = trajectory[-1]
        if self.validate(end_state, final_state):
            return 1.0
        return self.match_ratio(end_state, final_state)

    def _dicts_match(self, a: dict, b: dict) -> bool:
        if not a or not b:
            return a == b
        shared_keys = set(a.keys()) & set(b.keys())
        if not shared_keys:
            return False
        matches = sum(1 for k in shared_keys if a[k] == b[k])
        return matches / len(shared_keys) >= 0.8

    def _lists_match(self, a: list, b: list) -> bool:
        if not a or not b:
            return a == b
        shared = set(a) & set(b)
        return len(shared) / max(len(set(a) | set(b)), 1) >= 0.7
