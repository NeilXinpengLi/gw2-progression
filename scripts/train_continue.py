"""Continue training: generate large dataset + train sklearn model.

Runs the full loop:
  1. Load real account data (if available) or use rich synthetic
  2. Generate 500+ training events with realistic variations
  3. Train Random Forest model
  4. Save artifacts and report metrics
  5. Optional: run multiple rounds with increasing data
"""

from __future__ import annotations

import json
import random
import sys
import time
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(SRC.parent))

from gw2_progression.trainer.worker import TrainingWorker  # noqa: E402


def generate_events(count: int = 500) -> list[dict]:
    """Generate realistic training events with varied factors and outcomes."""
    events = []
    rng = random.Random(42)

    for i in range(count):
        liquid = round(rng.uniform(0.1, 0.95), 3)
        risk = round(rng.uniform(0.05, 0.8), 3)
        volatility = round(rng.uniform(0.05, 0.7), 3)
        goal_progress = round(rng.uniform(0.0, 1.0), 3)
        crafting = round(rng.uniform(0.0, 0.6), 3)
        seasonal = round(rng.uniform(0.0, 0.4), 3)

        score = round(0.3 + liquid * 0.5 - risk * 0.3 + goal_progress * 0.2 + rng.uniform(-0.1, 0.1), 3)
        confidence = round(0.5 + liquid * 0.3 - volatility * 0.2 + rng.uniform(-0.1, 0.1), 3)
        score = max(0.0, min(1.0, score))
        confidence = max(0.0, min(1.0, confidence))

        if score > 0.65 and liquid > 0.5 and risk < 0.4:
            decision = "APPROVE"
            success = True
            value_delta = int(rng.gauss(10000, 3000))
        elif score < 0.4 or risk > 0.65:
            decision = "REJECT"
            success = False
            value_delta = int(rng.gauss(-2000, 1000))
        else:
            decision = "REVIEW"
            success = rng.random() > 0.5
            value_delta = int(rng.gauss(2000, 4000))

        node_count = rng.randint(5, 50)
        edge_count = rng.randint(3, node_count * 2)

        events.append({
            "id": f"train-{i:04d}",
            "state": {
                "nodes": [{"id": f"n{j}"} for j in range(node_count)],
                "edges": [{"source": f"n{j}", "target": f"n{(j+1)%node_count}"} for j in range(edge_count)],
            },
            "decision": {"decision": decision, "score": score, "confidence": confidence},
            "outcome": {"success": success, "value_delta": value_delta, "time_saved_hours": rng.randint(0, 8)},
            "factors": [
                {"name": "liquid_wealth", "value": liquid, "weight": 0.25},
                {"name": "asset_risk", "value": risk, "weight": 0.20},
                {"name": "market_volatility", "value": volatility, "weight": 0.15},
                {"name": "goal_progress", "value": goal_progress, "weight": 0.20},
                {"name": "crafting_complexity", "value": crafting, "weight": 0.10},
                {"name": "seasonal_velocity", "value": seasonal, "weight": 0.10},
            ],
            "agent_type": "expert_reasoner",
            "timestamp": time.time() + i,
        })
    return events


def generate_multi_strategy_events(base_count: int = 200) -> list[dict]:
    """Generate events from multiple strategies (balanced, gold, build, legendary)."""
    events = []
    strategies = [
        {"name": "balanced", "liquid_bias": 0.5, "risk_bias": 0.3, "goal_bias": 0.5},
        {"name": "gold", "liquid_bias": 0.8, "risk_bias": 0.5, "goal_bias": 0.2},
        {"name": "build", "liquid_bias": 0.3, "risk_bias": 0.2, "goal_bias": 0.7},
        {"name": "legendary", "liquid_bias": 0.4, "risk_bias": 0.6, "goal_bias": 0.9},
    ]
    rng = random.Random(123)
    for strategy in strategies:
        for i in range(base_count // len(strategies)):
            liquid = round(rng.uniform(0.1, 0.95) * strategy["liquid_bias"] + rng.uniform(0.1, 0.3), 3)
            risk = round(rng.uniform(0.05, 0.8) * strategy["risk_bias"] + rng.uniform(0.05, 0.2), 3)
            goal_progress = round(rng.uniform(0.0, 1.0) * strategy["goal_bias"] + rng.uniform(0.0, 0.2), 3)
            liquid = min(1.0, liquid)
            risk = min(1.0, risk)
            goal_progress = min(1.0, goal_progress)

            score = round(0.3 + liquid * 0.4 - risk * 0.3 + goal_progress * 0.3 + rng.uniform(-0.1, 0.1), 3)
            score = max(0.0, min(1.0, score))

            if strategy["name"] == "gold" and liquid > 0.6:
                decision = "APPROVE"
                success = True
            elif strategy["name"] == "legendary" and goal_progress > 0.5:
                decision = "APPROVE"
                success = True
            elif score > 0.6:
                decision = "APPROVE"
                success = rng.random() > 0.2
            elif score < 0.35:
                decision = "REJECT"
                success = False
            else:
                decision = "REVIEW"
                success = rng.random() > 0.5

            events.append({
                "id": f"multi-{strategy['name']}-{i:03d}",
                "state": {
                    "nodes": [{"id": f"n{j}"} for j in range(rng.randint(5, 40))],
                    "edges": [{"source": f"n{j}", "target": f"n{j+1}"} for j in range(rng.randint(3, 30))],
                },
                "decision": {"decision": decision, "score": score, "confidence": round(0.5 + liquid * 0.3 - risk * 0.15, 3)},
                "outcome": {"success": success, "value_delta": int(rng.gauss(5000, 5000)), "time_saved_hours": rng.randint(0, 12)},
                "factors": [
                    {"name": "liquid_wealth", "value": liquid, "weight": 0.25},
                    {"name": "asset_risk", "value": risk, "weight": 0.20},
                    {"name": "goal_progress", "value": goal_progress, "weight": 0.25},
                    {"name": "strategy_align", "value": round(rng.uniform(0.3, 0.95), 3), "weight": 0.15},
                    {"name": "market_timing", "value": round(rng.uniform(0.1, 0.9), 3), "weight": 0.15},
                ],
                "agent_type": f"strategy_{strategy['name']}",
                "strategy": strategy["name"],
                "timestamp": time.time() + i,
            })
    return events


def main():
    rounds = [
        ("Round 1: 100 base events", 100),
        ("Round 2: +200 base events", 200),
        ("Round 3: +300 events + multi-strategy", 500),
        ("Round 4: +500 events (final)", 500),
    ]

    worker = TrainingWorker(checkpoint_dir="data/trainer_models", min_batch=50)
    total_events = 0

    print("=" * 64)
    print("  GW2 Expert AI — Continuing Training")
    print("=" * 64)

    for label, count in rounds:
        print(f"\n{label}...")
        base = generate_events(count)
        multi = generate_multi_strategy_events(count // 2)
        batch = base + multi
        total_events += len(batch)
        result = worker.run_once(batch)
        print(f"  Total: {result['total']}, Models: {result['models']}")

    print(f"\n{'=' * 64}")
    print("  Training Complete")
    print(f"  Total events processed: {total_events}")
    print(f"  Models trained:         {worker.model_count}")
    print(f"{'=' * 64}")

    models_dir = Path("data/trainer_models")
    for f in sorted(models_dir.glob("*.json")):
        meta = json.loads(f.read_text(encoding="utf-8"))
        print(f"  [{meta['status']}] {meta['model_id'][:12]} acc={meta.get('accuracy','?'):.4f} f1={meta.get('f1_weighted','?'):.4f} samples={meta.get('train_samples',0)+meta.get('test_samples',0)}")


if __name__ == "__main__":
    main()
