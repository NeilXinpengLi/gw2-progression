from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

from gw2_progression.data_acquisition.registry.source_registry import SourceConfig, SourceRegistry


class TaskFrequency(str, Enum):
    REALTIME = "realtime"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"


@dataclass
class ScheduledTask:
    source_id: str
    frequency: TaskFrequency
    last_run: float = 0.0
    run_count: int = 0
    enabled: bool = True
    handler: Callable[[SourceConfig], Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "frequency": self.frequency.value,
            "run_count": self.run_count,
            "enabled": self.enabled,
        }


@dataclass
class RefreshQueueItem:
    source_id: str
    reason: str
    priority: int
    entity_type: str | None = None
    entity_id: str | None = None
    enqueued_at: float = 0.0
    attempts: int = 0
    status: str = "pending"

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "reason": self.reason,
            "priority": self.priority,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "enqueued_at": self.enqueued_at,
            "attempts": self.attempts,
            "status": self.status,
        }


class TaskScheduler:
    """Task scheduler for periodic data ingestion.

    Manages when each source should be ingested based on its frequency.
    """

    def __init__(self, registry: SourceRegistry | None = None) -> None:
        self.registry = registry or SourceRegistry()
        self.tasks: dict[str, ScheduledTask] = {}
        self._build_tasks()
        self._run_history: list[dict[str, Any]] = []
        self._refresh_queue: list[RefreshQueueItem] = []

    def _build_tasks(self) -> None:
        for source in self.registry.get_enabled():
            freq = source.frequency
            if freq in [t.value for t in TaskFrequency]:
                self.tasks[source.id] = ScheduledTask(
                    source_id=source.id,
                    frequency=TaskFrequency(freq),
                    enabled=source.enabled,
                )

    def register_handler(self, source_id: str, handler: Callable[[SourceConfig], Any]) -> None:
        if source_id in self.tasks:
            self.tasks[source_id].handler = handler

    def get_pending(self, current_time: float, frequency: TaskFrequency) -> list[ScheduledTask]:
        interval_map = {
            TaskFrequency.REALTIME: 0,
            TaskFrequency.HOURLY: 3600,
            TaskFrequency.DAILY: 86400,
            TaskFrequency.WEEKLY: 604800,
        }
        interval = interval_map.get(frequency, 3600)
        return [
            t for t in self.tasks.values()
            if t.enabled and t.frequency == frequency and (current_time - t.last_run) >= interval
        ]

    def run_pending(self, current_time: float) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for freq in TaskFrequency:
            pending = self.get_pending(current_time, freq)
            for task in pending:
                source = self.registry.get(task.source_id)
                if source and task.handler:
                    try:
                        task.handler(source)
                        task.last_run = current_time
                        task.run_count += 1
                        results.append({
                            "source_id": task.source_id,
                            "status": "completed",
                            "frequency": freq.value,
                        })
                    except Exception as e:
                        results.append({
                            "source_id": task.source_id,
                            "status": "failed",
                            "error": str(e),
                            "frequency": freq.value,
                        })
        self._run_history.extend(results)
        return results

    def enqueue_refresh_requests(self, requests: list[dict[str, Any]], current_time: float | None = None) -> int:
        current_time = current_time if current_time is not None else 0.0
        existing = {
            (item.source_id, item.reason, item.entity_type, item.entity_id)
            for item in self._refresh_queue
            if item.status == "pending"
        }
        added = 0
        for request in requests:
            key = (request.get("source_id"), request.get("reason", "coverage_gap"), request.get("entity_type"), request.get("entity_id"))
            if not key[0] or key in existing:
                continue
            self._refresh_queue.append(RefreshQueueItem(
                source_id=str(key[0]),
                reason=str(key[1]),
                priority=int(request.get("priority", 3)),
                entity_type=key[2],
                entity_id=key[3],
                enqueued_at=current_time,
            ))
            existing.add(key)
            added += 1
        self._refresh_queue.sort(key=lambda item: (item.priority, item.enqueued_at, item.source_id))
        return added

    def run_refresh_queue(self, limit: int = 10) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        pending = [item for item in self._refresh_queue if item.status == "pending"][:limit]
        for item in pending:
            task = self.tasks.get(item.source_id)
            source = self.registry.get(item.source_id)
            item.attempts += 1
            if not task or not source or not task.handler:
                item.status = "blocked"
                results.append({**item.to_dict(), "status": "blocked", "error": "no handler"})
                continue
            try:
                task.handler(source)
                task.run_count += 1
                item.status = "completed"
                results.append({**item.to_dict(), "status": "completed"})
            except Exception as e:
                item.status = "failed"
                results.append({**item.to_dict(), "status": "failed", "error": str(e)})
        self._run_history.extend(results)
        return results

    def get_task(self, source_id: str) -> ScheduledTask | None:
        return self.tasks.get(source_id)

    def enable_task(self, source_id: str) -> bool:
        task = self.tasks.get(source_id)
        if task:
            task.enabled = True
            return True
        return False

    def disable_task(self, source_id: str) -> bool:
        task = self.tasks.get(source_id)
        if task:
            task.enabled = False
            return True
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_tasks": len(self.tasks),
            "enabled_tasks": sum(1 for t in self.tasks.values() if t.enabled),
            "recent_runs": len(self._run_history),
            "refresh_queue": {
                "pending": sum(1 for item in self._refresh_queue if item.status == "pending"),
                "completed": sum(1 for item in self._refresh_queue if item.status == "completed"),
                "failed": sum(1 for item in self._refresh_queue if item.status == "failed"),
                "items": [item.to_dict() for item in self._refresh_queue[-10:]],
            },
            "tasks": [t.to_dict() for t in self.tasks.values()],
        }
