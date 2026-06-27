"""Event Bus — async in-process event system with typed events and background workers.

MVP uses asyncio.Queue. Can be swapped for Redis/Kafka later without
changing consumer code.

Event types:
  - AUDIT:     Non-critical audit logging
  - ONTOLOGY:  Ontology graph sync (account, goals, builds)
  - REPORT:    Report generation
  - MARKET:    Market data refresh
"""

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine

logger = logging.getLogger("gw2.event_bus")


class EventType(Enum):
    AUDIT = "audit"
    ONTOLOGY = "ontology"
    REPORT = "report"
    MARKET = "market"


@dataclass
class Event:
    event_type: EventType
    payload: dict[str, Any] = field(default_factory=dict)
    source: str = ""


Handler = Callable[[Event], Coroutine[Any, Any, None]]

_queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=1000)
_handlers: dict[EventType, list[Handler]] = {}
_worker_task: asyncio.Task | None = None


def on(event_type: EventType) -> Callable[[Handler], Handler]:
    """Decorator to register an event handler."""
    def decorator(handler: Handler) -> Handler:
        _handlers.setdefault(event_type, []).append(handler)
        logger.debug("Handler registered for %s: %s", event_type.value, handler.__name__)
        return handler
    return decorator


def emit(event_type: EventType, payload: dict[str, Any] | None = None, source: str = "") -> None:
    """Fire-and-forget: push event to queue. Never blocks."""
    event = Event(event_type=event_type, payload=payload or {}, source=source)
    try:
        _queue.put_nowait(event)
    except asyncio.QueueFull:
        logger.warning("Event bus queue full, dropping %s event from %s", event_type.value, source)


async def emit_async(event_type: EventType, payload: dict[str, Any] | None = None, source: str = "") -> None:
    """Awaitable emit for when backpressure matters."""
    event = Event(event_type=event_type, payload=payload or {}, source=source)
    await _queue.put(event)


def start() -> None:
    global _worker_task
    if _worker_task is None:
        _worker_task = asyncio.create_task(_drain_loop())
        logger.info("Event bus worker started")


async def stop() -> None:
    global _worker_task
    if _worker_task is not None:
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass
        _worker_task = None
        await _flush()
        logger.info("Event bus worker stopped")


async def _drain_loop() -> None:
    while True:
        try:
            event = await _queue.get()
            await _dispatch(event)
            _queue.task_done()
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("Event bus worker error")


async def _dispatch(event: Event) -> None:
    handlers = _handlers.get(event.event_type, [])
    if not handlers:
        logger.debug("No handlers for event type: %s", event.event_type.value)
        return
    for handler in handlers:
        try:
            await handler(event)
        except Exception as e:
            logger.error("Handler %s failed for %s event: %s", handler.__name__, event.event_type.value, e)


async def _flush() -> None:
    """Drain remaining events on shutdown."""
    while not _queue.empty():
        try:
            event = _queue.get_nowait()
            await _dispatch(event)
            _queue.task_done()
        except asyncio.QueueEmpty:
            break
