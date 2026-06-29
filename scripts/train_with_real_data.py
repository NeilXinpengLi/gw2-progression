"""Train with real GW2 account data from the API key.

Fetches Netro.7195 account data, generates realistic training events
from the actual account state, and trains models on real-ish data.
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


def fetch_real_account() -> dict:
    """Fetch real GW2 account data."""
    from gw2_progression.analyzer import fetch_all
    from gw2_progression.expert_ai.adapters import account_contents_to_runtime_payload

    if not API_KEY:
        raise RuntimeError("GW2_API_KEY is required for real-data training")
    contents = asyncio.run(fetch_all(API_KEY))
    print(f"  Account: {contents.account_name}")
    print(f"  Characters: {len(contents.characters or [])}")
    print(f"  Wallet currencies: {len(contents.wallet or [])}")
    print(f"  Bank slots: {len(contents.bank or [])}")
    print(f"  Materials: {len(contents.materials or [])}")
    print(f"  Achievements: {len(contents.achievements or [])}")
    print(f"  Errors: {contents.errors}")

    payload = account_contents_to_runtime_payload(contents, item_limit=300)
    return {
        "contents": contents,
        "payload": payload,
        "account_name": contents.account_name or "unknown",
        "char_count": len(contents.characters or []),
        "item_count": len(contents.bank or []) + len(contents.materials or []),
    }


def generate_real_events(account_data: dict, count: int = 500) -> list[dict]:
    """Generate training events grounded in real account data."""
    from gw2_progression.bors.business_decision import DecisionEngine, DecisionFactor

    engine = DecisionEngine()
    rng = random.Random(int(time.time()))
    events = []

    contents = account_data["contents"]
    char_count = len(contents.characters or [])
    wallet = {str(c.get("id", 0)): c.get("value", 0) for c in (contents.wallet or [])}
    gold = wallet.get("1", 0)  # coin wallet
    materials_count = len(contents.materials or [])
    achievement_count = len(contents.achievements or [])
    has_guilds = bool(contents.guilds)

    # Ground truth stats from real account
    base_state = {
        "char_count": char_count,
        "gold_coins": gold,
        "materials_count": materials_count,
        "achievement_count": achievement_count,
        "has_guilds": has_guilds,
        "has_tp": contents.tradingpost_buys is not None,
    }
    print(f"  Base state: {json.dumps(base_state, indent=2)}")

    for i in range(count):
        # Wide-ranging factor values to exercise all decision outcomes
        (i / count) * 2 * 3.14159
        liquid = round(min(0.98, max(0.02, 0.5 + 0.45 * (i % 3 - 1) * rng.random())), 3)
        risk = round(min(0.9, max(0.02, 0.4 + 0.4 * rng.uniform(-1, 1))), 3)
        volatility = round(min(0.8, max(0.02, 0.3 + 0.3 * rng.uniform(-1, 1))), 3)
        goal_progress = round(min(1.0, max(0.0, rng.betavariate(2 + i % 5, 3))), 3)
        crafting = round(min(0.8, max(0.0, materials_count / 800 + 0.3 * rng.uniform(-1, 1))), 3)
        seasonal = round(min(0.5, max(0.0, 0.15 + 0.15 * rng.uniform(-1, 1))), 3)

        # Occasionally force high/low values to ensure class balance
        if i % 7 == 0:
            liquid = round(rng.uniform(0.7, 0.95), 3)
            risk = round(rng.uniform(0.05, 0.2), 3)
            goal_progress = round(rng.uniform(0.6, 0.95), 3)
        elif i % 11 == 0:
            liquid = round(rng.uniform(0.05, 0.2), 3)
            risk = round(rng.uniform(0.6, 0.85), 3)
            goal_progress = round(rng.uniform(0.0, 0.2), 3)

        factors = [
            DecisionFactor(name="liquid_wealth", value=liquid, weight=0.25, impact="positive"),
            DecisionFactor(name="asset_risk", value=risk, weight=0.20, impact="negative"),
            DecisionFactor(name="market_volatility", value=volatility, weight=0.15, impact="negative"),
            DecisionFactor(name="goal_progress", value=goal_progress, weight=0.20, impact="positive"),
            DecisionFactor(name="crafting_complexity", value=crafting, weight=0.10, impact="negative"),
            DecisionFactor(name="seasonal_velocity", value=seasonal, weight=0.10, impact="positive"),
        ]
        record = engine.decide("progression_recommendation", factors)

        score = record.score
        decision = record.decision.value
        confidence = record.confidence

        if i % 5 == 0:
            noise = rng.uniform(-0.15, 0.15)
            score = max(0.0, min(1.0, score + noise))
            if score > 0.6:
                decision = "APPROVE"
            elif score < 0.4:
                decision = "REJECT"
            else:
                decision = "REVIEW"

        if decision == "APPROVE":
            success = rng.random() > 0.15
            value_delta = int(max(500, rng.gauss(8000, 4000)))
        elif decision == "REJECT":
            success = rng.random() > 0.85
            value_delta = int(min(0, rng.gauss(-1000, 2000)))
        else:
            success = rng.random() > 0.4
            value_delta = int(rng.gauss(2000, 5000))

        events.append({
            "id": f"real-{i:04d}",
            "state": {
                "nodes": [{"id": f"n{j}"} for j in range(max(5, char_count * 3 + rng.randint(-5, 10)))],
                "edges": [{"source": f"n{j}", "target": f"n{j+1}"} for j in range(max(3, char_count * 2 + rng.randint(-3, 5)))],
            },
            "decision": {"decision": decision, "score": round(score, 4), "confidence": round(confidence, 4)},
            "outcome": {"success": success, "value_delta": value_delta, "time_saved_hours": rng.randint(0, 12)},
            "factors": [
                {"name": f.name, "value": f.value, "weight": f.weight} for f in factors
            ],
            "agent_type": "bors_real_data",
            "account": contents.account_name,
            "char_count": char_count,
            "total_gold": gold,
            "timestamp": time.time() + i,
        })

    return events


def main():
    print("=" * 64)
    print("  GW2 Expert AI — Training with REAL Account Data")
    print("=" * 64)

    print("\n[1/3] Fetching real account data from GW2 API...")
    account_data = fetch_real_account()

    print("\n[2/3] Generating training events from real account state...")
    events = generate_real_events(account_data, count=600)
    print(f"  Generated {len(events)} events")

    decisions = {}
    for e in events:
        d = e["decision"]["decision"]
        decisions[d] = decisions.get(d, 0) + 1
    print(f"  Decision distribution: {decisions}")

    print("\n[3/3] Training model on real account data...")
    from gw2_progression.trainer.worker import TrainingWorker
    worker = TrainingWorker(checkpoint_dir="data/trainer_models", min_batch=50)
    result = worker.run_once(events)

    print(f"\n{'=' * 64}")
    print("  Real Data Training Complete")
    print(f"  Events: {result['total']}")
    print(f"  Models trained this run: {result['models']}")
    print(f"  Total models: {worker.model_count}")
    print(f"{'=' * 64}")

    models_dir = Path("data/trainer_models")
    for f in sorted(models_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:3]:
        meta = json.loads(f.read_text(encoding="utf-8"))
        print(f"  [{meta['status']}] {meta['model_id'][:12]} "
              f"acc={meta.get('accuracy', 0):.4f} "
              f"f1={meta.get('f1_weighted', 0):.4f} "
              f"samples={meta.get('train_samples', 0) + meta.get('test_samples', 0)}")


if __name__ == "__main__":
    main()
