"""Prometheus-style metrics for GW2 Progression."""

import time
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class Metrics:
    requests_total: int = 0
    requests_active: int = 0
    analyses_total: int = 0
    errors_total: int = 0
    started_at: float = field(default_factory=time.time)
    # Per-endpoint latency buckets in ms
    endpoint_latency: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))
    # DB pool stats
    db_acquire_count: int = 0
    db_release_count: int = 0
    db_acquire_errors: int = 0

    def record_request(self, path: str, duration_ms: float, is_error: bool = False):
        self.requests_total += 1
        if is_error:
            self.errors_total += 1
        bucket = self.endpoint_latency[path]
        bucket.append(duration_ms)
        # Keep only last 100 samples per endpoint
        if len(bucket) > 100:
            bucket.pop(0)

    def _p50(self, values: list[float]) -> float:
        if not values:
            return 0.0
        sorted_v = sorted(values)
        return sorted_v[len(sorted_v) // 2]

    def _p95(self, values: list[float]) -> float:
        if not values:
            return 0.0
        sorted_v = sorted(values)
        return sorted_v[int(len(sorted_v) * 0.95)]

    def _p99(self, values: list[float]) -> float:
        if not values:
            return 0.0
        sorted_v = sorted(values)
        return sorted_v[int(len(sorted_v) * 0.99)]

    def snapshot(self) -> dict:
        uptime = int(time.time() - self.started_at)
        endpoints = {}
        for path, latencies in self.endpoint_latency.items():
            if latencies:
                endpoints[path] = {
                    "count": len(latencies),
                    "p50_ms": round(self._p50(latencies), 1),
                    "p95_ms": round(self._p95(latencies), 1),
                    "p99_ms": round(self._p99(latencies), 1),
                }
        return {
            "uptime_seconds": uptime,
            "requests_total": self.requests_total,
            "requests_active": self.requests_active,
            "analyses_total": self.analyses_total,
            "errors_total": self.errors_total,
            "error_rate_pct": round(self.errors_total / max(self.requests_total, 1) * 100, 2),
            "requests_per_sec": round(self.requests_total / max(uptime, 1), 2),
            "endpoints": endpoints,
            "db_acquire_count": self.db_acquire_count,
            "db_release_count": self.db_release_count,
            "db_acquire_errors": self.db_acquire_errors,
            "db_balance": self.db_acquire_count - self.db_release_count,
        }


metrics = Metrics()
