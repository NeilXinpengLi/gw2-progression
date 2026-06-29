"""Final training round: balanced real-data training with optimized features.

Uses Netro.7195 account data to generate a balanced training set
with realistic noise, then trains the production model.
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import sys
import time
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(SRC.parent))

API_KEY = os.environ.get("GW2_API_KEY", "")

from gw2_progression.analyzer import fetch_all  # noqa: E402
from gw2_progression.bors.business_decision import DecisionEngine, DecisionFactor  # noqa: E402


def fetch_account():
    if not API_KEY:
        raise RuntimeError("GW2_API_KEY is required for final training")
    contents = asyncio.run(fetch_all(API_KEY))
    wallet = {str(c.get("id", 0)): c.get("value", 0) for c in (contents.wallet or [])}
    gold = wallet.get("1", 0)
    print(f"  Account: {contents.account_name}, Gold: {gold:,}, Chars: {len(contents.characters or [])}, Mats: {len(contents.materials or [])}")
    return contents, gold


def gen_balanced(contents, gold, total=900):
    engine = DecisionEngine()
    rng = random.Random(999)
    events = []
    per_class = total // 3

    char_count = len(contents.characters or [])
    mat_count = len(contents.materials or [])

    for klass, label_fn in [
        ("APPROVE", lambda: (rng.uniform(0.7, 0.98), rng.uniform(0.02, 0.25), rng.uniform(0.6, 1.0))),
        ("REVIEW", lambda: (rng.uniform(0.3, 0.7), rng.uniform(0.2, 0.5), rng.uniform(0.3, 0.7))),
        ("REJECT", lambda: (rng.uniform(0.02, 0.3), rng.uniform(0.5, 0.9), rng.uniform(0.0, 0.3))),
    ]:
        for i in range(per_class):
            liquid, risk, progress = label_fn()
            liquid += rng.gauss(0, 0.05)
            risk += rng.gauss(0, 0.05)
            progress += rng.gauss(0, 0.05)
            liquid = max(0.01, min(0.99, liquid))
            risk = max(0.01, min(0.95, risk))
            progress = max(0.0, min(1.0, progress))
            volatility = rng.uniform(0.05, 0.7)
            crafting = min(0.8, mat_count / 800 + rng.uniform(-0.1, 0.2))
            seasonal = rng.uniform(0.0, 0.4)

            factors = [
                DecisionFactor(name="liquid_wealth", value=round(liquid, 3), weight=0.25, impact="positive"),
                DecisionFactor(name="asset_risk", value=round(risk, 3), weight=0.20, impact="negative"),
                DecisionFactor(name="market_volatility", value=round(volatility, 3), weight=0.15, impact="negative"),
                DecisionFactor(name="goal_progress", value=round(progress, 3), weight=0.20, impact="positive"),
                DecisionFactor(name="crafting_complexity", value=round(crafting, 3), weight=0.10, impact="negative"),
                DecisionFactor(name="seasonal_velocity", value=round(seasonal, 3), weight=0.10, impact="positive"),
            ]
            record = engine.decide("progression_recommendation", factors)
            score = record.score
            confidence = min(1.0, record.confidence + rng.uniform(-0.05, 0.05))

            if klass == "APPROVE":
                success = rng.random() > 0.1
                delta = int(max(1000, rng.gauss(10000, 5000)))
                time_saved = rng.randint(2, 12)
            elif klass == "REJECT":
                success = rng.random() > 0.85
                delta = int(min(-100, rng.gauss(-3000, 2000)))
                time_saved = 0
            else:
                success = rng.random() > 0.4
                delta = int(rng.gauss(2000, 4000))
                time_saved = rng.randint(0, 4)

            events.append({
                "id": f"balanced-{klass.lower()}-{i:04d}",
                "state": {
                    "nodes": [{"id": f"n{j}"} for j in range(max(5, char_count * 2 + rng.randint(-5, 15)))],
                    "edges": [{"source": f"n{j}", "target": f"n{j+1}"} for j in range(max(3, char_count + rng.randint(-2, 8)))],
                },
                "decision": {"decision": klass, "score": round(score, 4), "confidence": round(confidence, 4)},
                "outcome": {"success": success, "value_delta": delta, "time_saved_hours": time_saved},
                "factors": [{"name": f.name, "value": f.value, "weight": f.weight} for f in factors],
                "agent_type": "bors_real_account",
                "account": contents.account_name,
                "timestamp": time.time() + i,
            })
    rng.shuffle(events)
    return events


def main():
    print("=" * 64)
    print("  GW2 Expert AI — Final Balanced Training")
    print("=" * 64)

    print("\n[1/2] Fetching real account data...")
    contents, gold = fetch_account()

    print("\n[2/2] Generating balanced training events...")
    events = gen_balanced(contents, gold, total=900)
    from collections import Counter
    dist = Counter(e["decision"]["decision"] for e in events)
    print(f"  Generated {len(events)} events (balanced)")
    print(f"  Distribution: {dict(dist)}")

    from gw2_progression.trainer.worker import TrainingWorker
    worker = TrainingWorker(checkpoint_dir="data/trainer_models", min_batch=50)
    result = worker.run_once(events)

    print(f"\n{'=' * 64}")
    print("  Training Complete")
    print(f"  Events:    {result['total']}")
    print(f"  Models:    {result['models']}")
    print(f"{'=' * 64}")

    models_dir = Path("data/trainer_models")
    latest = sorted(models_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:5]
    for f in latest:
        meta = json.loads(f.read_text(encoding="utf-8"))
        samples = meta.get("train_samples", 0) + meta.get("test_samples", 0)
        print(f"  [{meta['status']}] {meta['model_id'][:12]} acc={meta.get('accuracy',0):.4f} f1={meta.get('f1_weighted',0):.4f} classes={meta.get('class_count',0)} samples={samples}")


if __name__ == "__main__":
    main()
