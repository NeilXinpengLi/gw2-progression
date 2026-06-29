"""End-to-end test of the standalone training worker."""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(SRC.parent))

events = []
for i in range(30):
    events.append({
        "id": f"seed-{i}",
        "state": {"nodes": [{"id": f"n{j}"} for j in range(5 + i % 3)], "edges": []},
        "decision": {"decision": ["APPROVE", "REVIEW", "REJECT"][i % 3], "score": 0.3 + i * 0.02, "confidence": 0.5 + i * 0.01},
        "outcome": {"success": i % 2 == 0, "value_delta": i * 200, "time_saved_hours": i % 4},
        "factors": [
            {"name": "liquid_wealth", "value": 0.7, "weight": 1},
            {"name": "asset_risk", "value": 0.3, "weight": 1},
            {"name": "market_volatility", "value": 0.2, "weight": 1},
        ],
        "agent_type": "test",
        "timestamp": 1000 + i,
    })

from gw2_progression.trainer.worker import TrainingWorker  # noqa: E402

worker = TrainingWorker(checkpoint_dir=str(Path("data/trainer_models")), min_batch=10)
result = worker.run_once(events)
print(f"Total events: {result['total']}")
print(f"Models trained: {result['models']}")

for f in Path("data/trainer_models").glob("*"):
    size = f.stat().st_size
    print(f"  {f.name} ({size} bytes)")

print("\nTraining worker standalone test PASSED")
