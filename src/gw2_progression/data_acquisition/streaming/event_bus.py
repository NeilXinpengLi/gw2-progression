from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class DataEvent:
    source_id: str
    data_type: str
    data: dict[str, Any]
    timestamp: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


EventHandler = Callable[[DataEvent], None]


class EventBus:
    """Simple in-memory event bus for data events.

    Supports publish/subscribe pattern for streaming data.
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, list[EventHandler]] = {}
        self._event_history: list[DataEvent] = []

    def subscribe(self, data_type: str, handler: EventHandler) -> None:
        if data_type not in self._subscribers:
            self._subscribers[data_type] = []
        self._subscribers[data_type].append(handler)

    def unsubscribe(self, data_type: str, handler: EventHandler) -> bool:
        if data_type in self._subscribers and handler in self._subscribers[data_type]:
            self._subscribers[data_type].remove(handler)
            return True
        return False

    def publish(self, event: DataEvent) -> None:
        self._event_history.append(event)
        handlers = self._subscribers.get(event.data_type, []) + self._subscribers.get("*", [])
        for handler in handlers:
            try:
                handler(event)
            except Exception:
                pass

    def replay(self, data_type: str | None = None) -> list[DataEvent]:
        if data_type:
            return [e for e in self._event_history if e.data_type == data_type]
        return list(self._event_history)

    def clear_history(self) -> None:
        self._event_history.clear()

    def to_dict(self) -> dict[str, Any]:
        return {
            "subscriber_count": sum(len(h) for h in self._subscribers.values()),
            "event_types": list(self._subscribers.keys()),
            "event_history_count": len(self._event_history),
        }
