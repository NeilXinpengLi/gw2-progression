"""Training scheduler and model trainer for Expert AI."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ScheduledJob:
    id: str
    kind: str
    payload: dict[str, Any]
    interval_seconds: int = 0
    next_run_at: float = field(default_factory=time.time)
    status: str = "scheduled"


class ModelTrainer:
    """Deterministic model-training execution facade."""

    def __init__(self, artifact_dir: str | Path = "data/expert_ai_models") -> None:
        self.artifact_dir = Path(artifact_dir)

    def train(self, dataset: dict[str, Any], model_type: str = "expert_reasoner") -> dict[str, Any]:
        examples = dataset.get("examples", [])
        labeled = [example for example in examples if example.get("label", {}).get("quality") != "unlabeled"]
        artifact = {
            "id": str(uuid.uuid4()),
            "model_type": model_type,
            "dataset_version": dataset.get("version", "unknown"),
            "created_at": time.time(),
            "status": "trained" if examples else "empty",
        }
        metrics = {
            "example_count": len(examples),
            "labeled_count": len(labeled),
            "label_coverage": round(len(labeled) / max(len(examples), 1), 3),
            "estimated_quality": round(min(0.55 + len(labeled) * 0.1, 0.99), 3) if examples else 0.0,
        }
        artifact_path = self._write_artifact(artifact, metrics, dataset)
        return {"artifact": {**artifact, "path": str(artifact_path)}, "metrics": metrics}

    def _write_artifact(self, artifact: dict[str, Any], metrics: dict[str, Any], dataset: dict[str, Any]) -> Path:
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        path = self.artifact_dir / f"{artifact['id']}.json"
        path.write_text(json.dumps({"artifact": artifact, "metrics": metrics, "dataset": dataset}, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        return path


class TrainingScheduler:
    """In-process scheduler facade with optional Redis queue dispatch."""

    def __init__(self, system: Any) -> None:
        self.system = system
        self.jobs: dict[str, ScheduledJob] = {}
        self.trainer = ModelTrainer()

    def schedule(self, payload: dict[str, Any]) -> dict[str, Any]:
        job = ScheduledJob(
            id=str(uuid.uuid4()),
            kind=payload.get("kind", "train_run"),
            payload=payload.get("payload", {}),
            interval_seconds=int(payload.get("interval_seconds", 0)),
            next_run_at=float(payload.get("next_run_at", time.time())),
        )
        self.jobs[job.id] = job
        queued = self.system.persistence.enqueue_task({"type": job.kind, "payload": job.payload, "job_id": job.id})
        self.system.observability.record_flow("train.schedule", job.status, {"job_id": job.id, "queued": queued.get("queued", False)})
        return {"job": self._job_to_dict(job), "queue": queued}

    def run_due(self, now: float | None = None) -> dict[str, Any]:
        now = now or time.time()
        due = [job for job in self.jobs.values() if job.next_run_at <= now and job.status in {"scheduled", "completed"}]
        results = []
        for job in due:
            results.append(self.run_job(job.id))
        return {"run_count": len(results), "results": results}

    def run_job(self, job_id: str) -> dict[str, Any]:
        job = self.jobs[job_id]
        job.status = "running"
        if job.kind == "train_run":
            result = self.system.run_training_pipeline(job.payload)
        elif job.kind == "model_train":
            dataset = job.payload.get("dataset") or self.system.run_training_pipeline(job.payload).get("dataset", {})
            result = self.trainer.train(dataset, model_type=job.payload.get("model_type", "expert_reasoner"))
        elif job.kind == "agents_run":
            result = self.system.run_agents(job.payload)
        else:
            result = {"status": "ignored", "kind": job.kind}
        job.status = "completed"
        self.system.observability.record_flow("train.job", job.status, {"job_id": job.id, "kind": job.kind})
        if job.interval_seconds:
            job.next_run_at = time.time() + job.interval_seconds
        return {"job": self._job_to_dict(job), "result": result}

    def list_jobs(self) -> list[dict[str, Any]]:
        return [self._job_to_dict(job) for job in self.jobs.values()]

    def _job_to_dict(self, job: ScheduledJob) -> dict[str, Any]:
        return {
            "id": job.id,
            "kind": job.kind,
            "payload": job.payload,
            "interval_seconds": job.interval_seconds,
            "next_run_at": job.next_run_at,
            "status": job.status,
        }
