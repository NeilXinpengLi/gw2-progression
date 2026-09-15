"""Metrics and audit trail for Expert AI production flows."""

from __future__ import annotations

import time
import uuid
from collections import defaultdict
from typing import Any


class MetricsRegistry:
    def __init__(self) -> None:
        self.counters: dict[str, int] = defaultdict(int)
        self.gauges: dict[str, float] = {}

    def increment(self, name: str, value: int = 1) -> dict[str, Any]:
        self.counters[name] += value
        return {"name": name, "value": self.counters[name]}

    def gauge(self, name: str, value: float) -> dict[str, Any]:
        self.gauges[name] = value
        return {"name": name, "value": value}

    def snapshot(self) -> dict[str, Any]:
        return {"counters": dict(self.counters), "gauges": dict(self.gauges), "created_at": time.time()}


class AuditTrail:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def record(self, action: str, actor: str = "system", subject: str = "", metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        event = {
            "id": str(uuid.uuid4()),
            "action": action,
            "actor": actor,
            "subject": subject,
            "metadata": metadata or {},
            "created_at": time.time(),
        }
        self.events.append(event)
        return event

    def query(self, action: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        rows = [event for event in self.events if not action or event["action"] == action]
        return rows[-limit:]


class ObservabilityHub:
    def __init__(self) -> None:
        self.metrics = MetricsRegistry()
        self.audit = AuditTrail()

    def record_flow(self, action: str, status: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        self.metrics.increment(f"{action}.{status}")
        return self.audit.record(action=action, subject=status, metadata=metadata)

    def snapshot(self) -> dict[str, Any]:
        return {"metrics": self.metrics.snapshot(), "audit": self.audit.query(limit=20)}
