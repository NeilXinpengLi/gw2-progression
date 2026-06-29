"""Standalone training worker — runs as a separate Docker container.

Subscribes to Redis stream "training:events", collates batches, trains sklearn models,
and saves artifacts. Communicates with the rest of the system via:
  - Redis stream (receives training events)
  - Local checkpoint directory (writes model files)
  - Optional Postgres model registry (writes model metadata)

Usage:
  python -m gw2_progression.trainer.worker
  python -m gw2_progression.trainer.worker --checkpoint-dir /app/models
"""

from __future__ import annotations

import argparse
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gw2_progression.trainer.dataset_collator import DatasetCollator

# ── Optional Redis subscriber ─────────────────────────────────────────────

def _create_redis_reader(redis_url: str, stream_key: str = "training:events", consumer_group: str = "trainer", consumer_name: str | None = None):
    """Create a Redis stream reader for training events."""
    import redis as redis_lib

    client = redis_lib.Redis.from_url(redis_url)
    consumer_name = consumer_name or f"trainer-{uuid.uuid4().hex[:8]}"

    try:
        client.xgroup_create(stream_key, consumer_group, id="0", mkstream=True)
    except redis_lib.ResponseError as e:
        if "BUSYGROUP" not in str(e):
            raise

    def read_batch(count: int = 10, block_ms: int = 5000) -> list[dict[str, Any]]:
        try:
            results = client.xreadgroup(consumer_group, consumer_name, {stream_key: ">"}, count=count, block=block_ms)
        except redis_lib.ResponseError:
            return []
        events = []
        if results:
            for stream_name, messages in results:
                for msg_id, msg_data in messages:
                    event = {k.decode() if isinstance(k, bytes) else k: v for k, v in msg_data.items()}
                    if isinstance(event.get("payload", ""), (bytes, str)):
                        try:
                            event = json.loads(event["payload"] if isinstance(event["payload"], str) else event["payload"].decode())
                        except (json.JSONDecodeError, TypeError):
                            pass
                    events.append(event)
                    try:
                        client.xack(stream_key, consumer_group, msg_id)
                    except Exception:
                        pass
        return events

    return read_batch


# ── Model Trainer (sklearn) ───────────────────────────────────────────────

def _train_sklearn_model(X, y, artifacts_dir: Path) -> dict[str, Any]:
    """Train a sklearn Random Forest classifier and save artifacts."""
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import accuracy_score, f1_score
    from sklearn.model_selection import train_test_split

    if X.shape[0] < 5:
        return {"status": "insufficient_data", "samples": X.shape[0]}

    seed = int(time.time())
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=seed, stratify=y if len(set(y)) > 1 else None)

    model = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=seed, class_weight="balanced", n_jobs=-1)
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    accuracy = float(accuracy_score(y_test, y_pred))
    f1 = float(f1_score(y_test, y_pred, average="weighted")) if len(set(y_test)) > 1 else accuracy

    model_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()
    artifact = {
        "model_id": model_id,
        "model_type": "random_forest_v1",
        "train_samples": int(X_train.shape[0]),
        "test_samples": int(X_test.shape[0]),
        "feature_count": int(X.shape[1]),
        "class_count": int(len(set(y))),
        "accuracy": round(accuracy, 4),
        "f1_weighted": round(f1, 4),
        "feature_importance": [round(float(v), 4) for v in model.feature_importances_],
        "timestamp": timestamp,
        "status": "trained",
    }

    import joblib
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    model_path = artifacts_dir / f"{model_id}.joblib"
    joblib.dump({"model": model, "artifact": artifact, "classes": model.classes_.tolist()}, model_path)

    meta_path = artifacts_dir / f"{model_id}.json"
    meta_path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False), encoding="utf-8")

    artifact["path"] = str(model_path)
    artifact["meta_path"] = str(meta_path)

    print(f"[TRAINER] Model {model_id[:12]} trained: acc={accuracy:.4f} f1={f1:.4f} samples={X.shape[0]} features={X.shape[1]} classes={len(set(y))}")
    return artifact


# ── Main training loop ────────────────────────────────────────────────────

class TrainingWorker:
    """Standalone training worker process."""

    def __init__(self, checkpoint_dir: str = "data/models", redis_url: str | None = None, min_batch: int = 20):
        self.checkpoint_dir = Path(checkpoint_dir)
        self.min_batch = min_batch
        self.collator = DatasetCollator(max_samples=50000)
        self.redis_reader = None
        self.model_count = 0

        if redis_url:
            try:
                self.redis_reader = _create_redis_reader(redis_url)
                print(f"[TRAINER] Connected to Redis: {redis_url}")
            except Exception as e:
                print(f"[TRAINER] Redis connection failed ({e}), running in file-only mode")

    def add_training_event(self, event: dict[str, Any]) -> None:
        self.collator.add_event(event)
        print(f"[TRAINER] Event added: {event.get('id', '?')[:12]} (total: {self.collator.count})", flush=True)

        if self.collator.count >= self.min_batch:
            self._train_and_save()

    def add_training_events(self, events: list[dict[str, Any]]) -> None:
        for event in events:
            self.collator.add_event(event)
        print(f"[TRAINER] Batch added: {len(events)} events (total: {self.collator.count})", flush=True)

        if self.collator.count >= self.min_batch:
            self._train_and_save()

    def _train_and_save(self) -> dict[str, Any] | None:
        X, y = self.collator.collate()
        if X.shape[0] < self.min_batch:
            return None

        result = _train_sklearn_model(X, y, self.checkpoint_dir)
        if result.get("status") == "trained":
            self.model_count += 1

        dataset_path = self.checkpoint_dir / f"dataset_{result['model_id']}.npz"
        self.collator.save(str(dataset_path))
        return result

    def run_once(self, events: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        if events:
            self.add_training_events(events)
        elif self.redis_reader:
            events = self.redis_reader(count=50, block_ms=3000)
            if events:
                self.add_training_events(events)
        return {"total": self.collator.count, "models": self.model_count}

    def run_loop(self, interval_seconds: int = 10):
        """Main loop: poll Redis, collate, train."""
        if not self.redis_reader:
            print("[TRAINER] No Redis reader available. Use --redis-url or feed events via run_once()")
            return

        print(f"[TRAINER] Starting training loop (interval={interval_seconds}s, min_batch={self.min_batch})")
        while True:
            try:
                events = self.redis_reader(count=100, block_ms=interval_seconds * 1000)
                if events:
                    self.add_training_events(events)
            except KeyboardInterrupt:
                print("[TRAINER] Shutting down")
                break
            except Exception as e:
                print(f"[TRAINER] Error: {e}", flush=True)
                time.sleep(5)


# ── CLI ────────────────────────────────────────────────────────────────────

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="GW2 Progression Training Worker")
    p.add_argument("--checkpoint-dir", default=os.getenv("TRAINER_CHECKPOINT_DIR", "data/models"), help="Model checkpoint directory")
    p.add_argument("--redis-url", default=os.getenv("EXPERT_AI_REDIS_URL", ""), help="Redis URL for training event stream")
    p.add_argument("--min-batch", type=int, default=int(os.getenv("TRAINER_MIN_BATCH", "20")), help="Minimum events before training")
    p.add_argument("--interval", type=int, default=int(os.getenv("TRAINER_INTERVAL", "10")), help="Poll interval in seconds")
    p.add_argument("--once", action="store_true", help="Run one training cycle and exit")
    p.add_argument("--seed-file", default="", help="Load seed events from a JSON file")
    return p.parse_args(argv)


def main() -> None:
    args = _parse_args()
    worker = TrainingWorker(checkpoint_dir=args.checkpoint_dir, redis_url=args.redis_url, min_batch=args.min_batch)

    if args.seed_file:
        path = Path(args.seed_file)
        if path.exists():
            raw = json.loads(path.read_text(encoding="utf-8"))
            events = raw if isinstance(raw, list) else raw.get("events", [raw])
            worker.add_training_events(events)
            print(f"[TRAINER] Loaded {len(events)} seed events from {args.seed_file}")

    if args.once:
        result = worker.run_once()
        print(json.dumps(result, indent=2))
        return

    worker.run_loop(interval_seconds=args.interval)


if __name__ == "__main__":
    main()
