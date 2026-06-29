from __future__ import annotations

import random
import random as _random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CalibratedParameter(str, Enum):
    FARM_YIELD_MULTIPLIER = "farm_yield_multiplier"
    CRAFT_SUCCESS_RATE = "craft_success_rate"
    MARKET_VOLATILITY = "market_volatility"
    ACHIEVEMENT_DIFFICULTY = "achievement_difficulty"
    TRADE_SPREAD = "trade_spread"
    DROP_RATE_MULTIPLIER = "drop_rate_multiplier"
    GOLD_INFLATION = "gold_inflation"
    AGENT_RISK_TOLERANCE = "agent_risk_tolerance"


@dataclass
class CalibrationMetric:
    """A single calibration measurement."""

    name: str
    simulated_value: float
    real_value: float
    error: float
    weight: float = 1.0

    @property
    def absolute_error(self) -> float:
        return abs(self.error)

    @property
    def relative_error(self) -> float:
        if self.real_value == 0:
            return 1.0 if self.simulated_value != 0 else 0.0
        return abs(self.error) / abs(self.real_value)


@dataclass
class CalibrationObservation:
    """A full calibration observation at one snapshot."""

    timestamp: int
    metrics: list[CalibrationMetric]
    parameter_adjustments: dict[str, float] = field(default_factory=dict)
    total_loss: float = 0.0


class CalibrationLoop:
    """Closed-loop simulation calibration.

    Compares simulated state to real (API) snapshots and adjusts
    simulation parameters to minimize consistency loss.

    loss = Σ w_i * |real_i - simulated_i| / max(|real_i|, ε)
    """

    def __init__(
        self,
        learning_rate: float = 0.05,
        momentum: float = 0.3,
        snapshot_interval: int = 10,
    ) -> None:
        self.learning_rate = learning_rate
        self.momentum = momentum
        self.snapshot_interval = snapshot_interval
        self.parameters: dict[str, float] = {
            CalibratedParameter.FARM_YIELD_MULTIPLIER.value: 1.0,
            CalibratedParameter.CRAFT_SUCCESS_RATE.value: 0.85,
            CalibratedParameter.MARKET_VOLATILITY.value: 0.15,
            CalibratedParameter.ACHIEVEMENT_DIFFICULTY.value: 1.0,
            CalibratedParameter.TRADE_SPREAD.value: 0.15,
            CalibratedParameter.DROP_RATE_MULTIPLIER.value: 1.0,
            CalibratedParameter.GOLD_INFLATION.value: 0.02,
            CalibratedParameter.AGENT_RISK_TOLERANCE.value: 0.5,
        }
        self._velocities: dict[str, float] = {k: 0.0 for k in self.parameters}
        self.observations: list[CalibrationObservation] = []
        self._step_count = 0
        self._trading_histories: dict[str, list[float]] = {}

    # ─── Metrics ────────────────────────────────────────────────────

    def compute_metrics(
        self,
        simulated: dict[str, Any],
        real: dict[str, Any],
    ) -> list[CalibrationMetric]:
        metrics: list[CalibrationMetric] = []

        metrics.append(self._compare_key("gold", simulated, real, weight=2.0))
        metrics.append(self._compare_key("inventory_size", simulated, real, weight=1.0))
        metrics.append(self._compare_key("achievement_count", simulated, real, weight=1.5))

        sim_market = simulated.get("market", {}) or {}
        real_market = real.get("market", {}) or {}
        if sim_market and real_market:
            price_error = self._compare_market_prices(sim_market, real_market)
            metrics.append(CalibrationMetric(
                name="market_price_alignment",
                simulated_value=price_error["sim_avg"],
                real_value=price_error["real_avg"],
                error=price_error["mape"],
                weight=1.0,
            ))

        metrics.append(self._compare_key("validation_match_count", simulated, real, weight=0.5))

        return metrics

    def _compare_key(self, key: str, sim: dict[str, Any], real: dict[str, Any], weight: float = 1.0) -> CalibrationMetric:
        if key == "inventory_size":
            sim_val = len(sim.get("inventory", {}) or {})
            real_val = len(real.get("inventory", {}) or {})
        elif key == "achievement_count":
            sim_val = len(sim.get("achievements", []) or [])
            real_val = len(real.get("achievements", []) or [])
        elif key == "validation_match_count":
            sim_val = len(sim.get("_action_validations", []) or [])
            real_val = len(real.get("_action_validations", []) or [])
        else:
            sim_val = sim.get(key, 0)
            real_val = real.get(key, 0)

        if isinstance(sim_val, (int, float)) and isinstance(real_val, (int, float)):
            error = sim_val - real_val
        else:
            error = 0.0

        return CalibrationMetric(
            name=key,
            simulated_value=float(sim_val) if isinstance(sim_val, (int, float)) else 0.0,
            real_value=float(real_val) if isinstance(real_val, (int, float)) else 0.0,
            error=float(error),
            weight=weight,
        )

    def _compare_market_prices(self, sim_market: dict[str, Any], real_market: dict[str, Any]) -> dict[str, float]:
        common = set(sim_market.keys()) & set(real_market.keys())
        if not common:
            return {"sim_avg": 0.0, "real_avg": 0.0, "mape": 0.0}
        sim_prices = [sim_market[k].get("price", 0) if isinstance(sim_market[k], dict) else sim_market[k] for k in common]
        real_prices = [real_market[k].get("price", 0) if isinstance(real_market[k], dict) else real_market[k] for k in common]
        sim_avg = sum(sim_prices) / len(sim_prices)
        real_avg = sum(real_prices) / len(real_prices)
        mape = sum(abs(s - r) / max(abs(r), 1.0) for s, r in zip(sim_prices, real_prices)) / len(common)
        return {"sim_avg": sim_avg, "real_avg": real_avg, "mape": mape}

    # ─── Loss ───────────────────────────────────────────────────────

    def compute_loss(self, metrics: list[CalibrationMetric]) -> float:
        total = 0.0
        for m in metrics:
            total += m.weight * m.relative_error
        return total / max(len(metrics), 1)

    # ─── Parameter Adjustment ───────────────────────────────────────

    def adjust_parameters(
        self,
        loss: float,
        metrics: list[CalibrationMetric],
        rng: random.Random | None = None,
    ) -> dict[str, float]:
        rng = rng or _random.Random()
        adjustments: dict[str, float] = {}
        gradient = loss * self.learning_rate

        for metric in metrics:
            if metric.name == "gold":
                adj = -gradient * 0.5
                self._apply_adjustment(CalibratedParameter.FARM_YIELD_MULTIPLIER.value, adj)
                self._apply_adjustment(CalibratedParameter.GOLD_INFLATION.value, adj * 0.2)
                adjustments[CalibratedParameter.FARM_YIELD_MULTIPLIER.value] = self.parameters[CalibratedParameter.FARM_YIELD_MULTIPLIER.value]
                adjustments[CalibratedParameter.GOLD_INFLATION.value] = self.parameters[CalibratedParameter.GOLD_INFLATION.value]

            elif metric.name == "inventory_size":
                adj = -gradient * 0.3
                self._apply_adjustment(CalibratedParameter.DROP_RATE_MULTIPLIER.value, adj)
                adjustments[CalibratedParameter.DROP_RATE_MULTIPLIER.value] = self.parameters[CalibratedParameter.DROP_RATE_MULTIPLIER.value]

            elif metric.name == "achievement_count":
                adj = gradient * 0.2
                self._apply_adjustment(CalibratedParameter.ACHIEVEMENT_DIFFICULTY.value, adj)
                adjustments[CalibratedParameter.ACHIEVEMENT_DIFFICULTY.value] = self.parameters[CalibratedParameter.ACHIEVEMENT_DIFFICULTY.value]

            elif metric.name == "market_price_alignment":
                adj = -gradient * 0.4
                self._apply_adjustment(CalibratedParameter.MARKET_VOLATILITY.value, adj)
                adjustments[CalibratedParameter.MARKET_VOLATILITY.value] = self.parameters[CalibratedParameter.MARKET_VOLATILITY.value]

        return adjustments

    def _apply_adjustment(self, param: str, delta: float) -> None:
        self._velocities[param] = self.momentum * self._velocities[param] + (1.0 - self.momentum) * delta
        self.parameters[param] = max(0.01, min(2.0, self.parameters[param] + self._velocities[param]))

    # ─── Main Loop ──────────────────────────────────────────────────

    def observe(
        self,
        simulated: dict[str, Any],
        real: dict[str, Any],
        rng: random.Random | None = None,
    ) -> CalibrationObservation:
        self._step_count += 1

        metrics = self.compute_metrics(simulated, real)
        loss = self.compute_loss(metrics)
        adjustments = self.adjust_parameters(loss, metrics, rng=rng)

        obs = CalibrationObservation(
            timestamp=self._step_count,
            metrics=metrics,
            parameter_adjustments=adjustments,
            total_loss=round(loss, 6),
        )
        self.observations.append(obs)
        return obs

    def should_calibrate(self) -> bool:
        return self._step_count % self.snapshot_interval == 0

    def get_parameter(self, name: str, default: float = 1.0) -> float:
        return self.parameters.get(name, default)

    def apply_to_state(self, state: dict[str, Any]) -> dict[str, Any]:
        """Apply calibrated parameters to a state dict for simulation."""
        state = dict(state)
        farm_mult = self.get_parameter(CalibratedParameter.FARM_YIELD_MULTIPLIER.value, 1.0)
        if farm_mult != 1.0 and "gold" in state:
            if isinstance(state["gold"], (int, float)):
                state["gold"] = int(state["gold"] * farm_mult)
        return state

    # ─── Calibration Stats ──────────────────────────────────────────

    @property
    def average_loss(self) -> float:
        if not self.observations:
            return 0.0
        return sum(o.total_loss for o in self.observations) / len(self.observations)

    @property
    def loss_trend(self) -> str:
        if len(self.observations) < 3:
            return "insufficient_data"
        recent = [o.total_loss for o in self.observations[-3:]]
        if recent[-1] < recent[0] * 0.9:
            return "improving"
        if recent[-1] > recent[0] * 1.1:
            return "diverging"
        return "stable"

    def best_metrics(self) -> dict[str, float]:
        if not self.observations:
            return {}
        best = min(self.observations, key=lambda o: o.total_loss)
        return {m.name: round(abs(m.error), 4) for m in best.metrics}

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_count": self._step_count,
            "parameters": dict(self.parameters),
            "average_loss": round(self.average_loss, 6),
            "loss_trend": self.loss_trend,
            "last_loss": round(self.observations[-1].total_loss, 6) if self.observations else None,
            "observation_count": len(self.observations),
            "best_metrics": self.best_metrics(),
        }
