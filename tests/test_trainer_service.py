"""Tests for the standalone Training Worker service."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from gw2_progression.trainer.dataset_collator import DatasetCollator, extract_features, extract_label
from gw2_progression.trainer.worker import TrainingWorker, _train_sklearn_model

# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def sample_event() -> dict:
    return {
        "id": "test-event-1",
        "state": {"nodes": [{"id": "n1"}, {"id": "n2"}], "edges": [{"source": "n1", "target": "n2"}]},
        "decision": {"decision": "APPROVE", "score": 0.85, "confidence": 0.78},
        "outcome": {"success": True, "value_delta": 5000, "time_saved_hours": 2},
        "factors": [
            {"name": "liquid_wealth", "value": 0.8, "weight": 0.6},
            {"name": "asset_risk", "value": 0.2, "weight": 0.4},
        ],
        "agent_type": "expert_reasoner",
        "timestamp": 1234567890,
    }


@pytest.fixture
def sample_events(sample_event) -> list[dict]:
    events = []
    for i in range(25):
        e = dict(sample_event)
        e["id"] = f"test-event-{i}"
        e["decision"]["score"] = 0.5 + (i % 5) * 0.1
        e["decision"]["decision"] = ["APPROVE", "REVIEW", "REJECT"][i % 3]
        e["outcome"]["success"] = i % 2 == 0
        e["outcome"]["value_delta"] = i * 100
        events.append(e)
    return events


# ── DatasetCollator Tests ─────────────────────────────────────────────────

class TestDatasetCollator:
    def test_empty_collator(self):
        c = DatasetCollator()
        X, y = c.collate()
        assert X.shape == (0, 13)
        assert y.shape == (0,)

    def test_add_event(self, sample_event):
        c = DatasetCollator()
        c.add_event(sample_event)
        assert c.count == 1
        X, y = c.collate()
        assert X.shape == (1, 13)
        assert y.shape == (1,)

    def test_add_events(self, sample_events):
        c = DatasetCollator()
        c.add_events(sample_events)
        assert c.count == 25

    def test_max_samples(self, sample_events):
        c = DatasetCollator(max_samples=10)
        c.add_events(sample_events)
        assert c.count == 10

    def test_save_and_load(self, sample_events, tmp_path):
        c = DatasetCollator()
        c.add_events(sample_events)
        path = tmp_path / "dataset.npz"
        saved = c.save(str(path))
        assert Path(saved).exists()
        X2, y2, meta = DatasetCollator.load(str(path))
        assert X2.shape[0] == 25
        assert "event_count" in meta

    def test_label_extraction(self, sample_event):
        sample_event["decision"]["decision"] = "APPROVE"
        sample_event["outcome"]["success"] = True
        assert extract_label(sample_event) == 2

        sample_event["decision"]["decision"] = "REJECT"
        sample_event["outcome"]["success"] = False
        assert extract_label(sample_event) == 0

        sample_event["decision"]["decision"] = "REVIEW"
        assert extract_label(sample_event) == 1

    def test_feature_extraction(self, sample_event):
        f = extract_features(sample_event)
        assert len(f) == 13
        assert f[0] == 2.0  # node count
        assert f[1] == 1.0  # edge count
        assert f[2] == 0.8  # liquid_wealth
        assert f[3] == 0.2  # asset_risk
        assert f[8] == 0.85  # decision score
        assert f[9] == 0.78  # decision confidence
        assert f[10] == 5000.0  # value_delta
        assert f[12] == 1.0  # success


# ── Model Trainer Tests ───────────────────────────────────────────────────

class TestModelTrainer:
    def test_insufficient_data(self, tmp_path):
        X = np.empty((3, 13), dtype=np.float32)
        y = np.array([0, 1, 2], dtype=np.int32)
        result = _train_sklearn_model(X, y, tmp_path)
        assert result["status"] == "insufficient_data"

    def test_trains_random_forest(self, sample_events, tmp_path):
        c = DatasetCollator()
        c.add_events(sample_events)
        X, y = c.collate()
        result = _train_sklearn_model(X, y, tmp_path)
        assert result["status"] == "trained"
        assert 0 <= result["accuracy"] <= 1
        assert result["feature_count"] == 13
        assert "model_id" in result
        assert "path" in result

        model_path = Path(result["path"])
        assert model_path.exists()

    def test_artifact_shape(self, sample_events, tmp_path):
        c = DatasetCollator()
        c.add_events(sample_events)
        X, y = c.collate()
        result = _train_sklearn_model(X, y, tmp_path)
        assert len(result["feature_importance"]) == 13


# ── TrainingWorker Tests ──────────────────────────────────────────────────

class TestTrainingWorker:
    def test_worker_initialization(self, tmp_path):
        worker = TrainingWorker(checkpoint_dir=str(tmp_path))
        assert worker.collator.count == 0
        assert worker.model_count == 0

    def test_worker_run_once_no_events(self, tmp_path):
        worker = TrainingWorker(checkpoint_dir=str(tmp_path), min_batch=5)
        result = worker.run_once()
        assert result["total"] == 0

    def test_worker_run_once_with_events(self, sample_events, tmp_path):
        worker = TrainingWorker(checkpoint_dir=str(tmp_path), min_batch=5)
        result = worker.run_once(sample_events)
        assert result["total"] == 25
        assert result["models"] == 1

    def test_worker_trains_after_min_batch(self, sample_event, tmp_path):
        worker = TrainingWorker(checkpoint_dir=str(tmp_path), min_batch=10)
        for i in range(5):
            worker.add_training_event(sample_event)
        assert worker.model_count == 0
        for i in range(10):
            e = dict(sample_event)
            e["id"] = f"extra-{i}"
            e["decision"]["score"] = 0.3 + i * 0.05
            e["outcome"]["success"] = i > 3
            worker.add_training_event(e)
        assert worker.model_count >= 1

    def test_worker_runs_standalone(self, sample_events, tmp_path):
        worker = TrainingWorker(checkpoint_dir=str(tmp_path), min_batch=5)
        worker.add_training_events(sample_events)
        assert (tmp_path / f"dataset_{worker.model_count > 0}.npz").exists() or worker.model_count > 0
        assert worker.collator.count == 25


# ── Publisher Tests ───────────────────────────────────────────────────────

class TestPublisher:
    def test_publish_training_event_no_redis(self):
        from gw2_progression.trainer.publisher import publish_training_event
        result = publish_training_event({"test": True})
        assert result is False

    def test_publish_from_training_pipeline_result(self):
        from gw2_progression.trainer.publisher import publish_from_training_pipeline
        result = publish_from_training_pipeline({
            "run_id": "test-123",
            "status": "completed",
            "etl": {"node_count": 10, "edge_count": 5},
            "metrics": {"estimated_quality": 0.75, "label_coverage": 1.0, "example_count": 5},
            "label": {"decision": {"decision": "APPROVE"}},
        })
        assert result is False  # no Redis available in test
