from __future__ import annotations

import time
from typing import Any

from gw2_progression.data_acquisition.streaming.event_bus import DataEvent, EventBus


class StreamEngine:
    """Real-time streaming update engine.

    Buffers incoming data events and flushes them in batches
    to the connected graph consumers.
    """

    def __init__(self, buffer_size: int = 100, flush_interval: float = 5.0) -> None:
        self.buffer_size = buffer_size
        self.flush_interval = flush_interval
        self.buffer: list[DataEvent] = []
        self.event_bus = EventBus()
        self._last_flush = time.time()
        self._total_pushed = 0
        self._total_flushed = 0

    def push(self, event: DataEvent) -> None:
        self.buffer.append(event)
        self._total_pushed += 1

        if len(self.buffer) >= self.buffer_size or (time.time() - self._last_flush) >= self.flush_interval:
            self.flush()

    def push_data(self, source_id: str, data_type: str, data: dict[str, Any]) -> None:
        event = DataEvent(
            source_id=source_id,
            data_type=data_type,
            data=data,
            timestamp=time.time(),
        )
        self.push(event)

    def flush(self) -> list[DataEvent]:
        if not self.buffer:
            return []
        batch = list(self.buffer)
        self.buffer.clear()
        self._last_flush = time.time()

        for event in batch:
            self.event_bus.publish(event)

        self._total_flushed += len(batch)
        return batch

    @property
    def buffer_size_current(self) -> int:
        return len(self.buffer)

    def subscribe(self, data_type: str, handler) -> None:
        self.event_bus.subscribe(data_type, handler)

    def to_dict(self) -> dict[str, Any]:
        return {
            "buffer_size": self.buffer_size,
            "flush_interval": self.flush_interval,
            "current_buffered": len(self.buffer),
            "total_pushed": self._total_pushed,
            "total_flushed": self._total_flushed,
            "subscribers": len(self.event_bus._subscribers),
        }
