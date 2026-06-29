from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TemporalSnapshot:
    t: int
    state: dict[str, Any]
    action: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class TemporalState:
    """Unified temporal state with global time axis T.

    All system layers synchronize on this single timeline:
      DGSK: structure at t
      OOSK: state transition t → t+1
      BORS: decision(t)
      LLM:  reasoning(t)
      RL:   policy(t)
    """

    def __init__(self, initial_state: dict[str, Any] | None = None) -> None:
        self.t: int = 0
        self._current: dict[str, Any] = copy.deepcopy(initial_state) if initial_state else {}
        self._history: list[TemporalSnapshot] = []
        self._snapshot_interval: int = 1

    @property
    def current(self) -> dict[str, Any]:
        return self._current

    @property
    def history(self) -> list[TemporalSnapshot]:
        return list(self._history)

    @property
    def age(self) -> int:
        return self.t

    def set_snapshot_interval(self, interval: int) -> None:
        self._snapshot_interval = max(1, interval)

    def advance(self, action: dict[str, Any] | None = None, steps: int = 1) -> dict[str, Any]:
        for _ in range(steps):
            if steps == 1 or self.t % self._snapshot_interval == 0:
                self._history.append(
                    TemporalSnapshot(
                        t=self.t,
                        state=copy.deepcopy(self._current),
                        action=copy.deepcopy(action) if action else None,
                    )
                )
            self.t += 1
        return self._current

    def apply_transition(self, new_state: dict[str, Any], action: dict[str, Any] | None = None) -> dict[str, Any]:
        self._history.append(
            TemporalSnapshot(
                t=self.t,
                state=copy.deepcopy(self._current),
                action=copy.deepcopy(action) if action else None,
            )
        )
        self.t += 1
        self._current = copy.deepcopy(new_state)
        return self._current

    def get_state_at(self, t: int) -> dict[str, Any] | None:
        if t == self.t:
            return self._current
        for snap in reversed(self._history):
            if snap.t == t:
                return snap.state
        return None

    def get_state_range(self, t_start: int, t_end: int) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for snap in self._history:
            if t_start <= snap.t <= t_end:
                results.append(snap.state)
        if t_start <= self.t <= t_end:
            results.append(self._current)
        return results

    def get_action_at(self, t: int) -> dict[str, Any] | None:
        for snap in reversed(self._history):
            if snap.t == t:
                return snap.action
        return None

    def delta(self, t1: int, t2: int) -> dict[str, Any]:
        s1 = self.get_state_at(t1) or {}
        s2 = self.get_state_at(t2) or {}
        delta: dict[str, Any] = {}
        all_keys = set(s1.keys()) | set(s2.keys())
        for k in all_keys:
            v1 = s1.get(k)
            v2 = s2.get(k)
            if v1 != v2:
                if isinstance(v1, dict) and isinstance(v2, dict):
                    inner: dict[str, Any] = {}
                    for ik in set(v1.keys()) | set(v2.keys()):
                        if v1.get(ik) != v2.get(ik):
                            inner[ik] = {"from": v1.get(ik), "to": v2.get(ik)}
                    if inner:
                        delta[k] = inner
                else:
                    delta[k] = {"from": v1, "to": v2}
        return delta

    def trajectory_length(self) -> int:
        return len(self._history) + 1

    def reset(self, initial_state: dict[str, Any] | None = None) -> None:
        self.t = 0
        self._current = copy.deepcopy(initial_state) if initial_state else {}
        self._history = []
