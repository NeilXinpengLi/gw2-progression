"""Worker entrypoint for the Expert AI deployment stack."""

from __future__ import annotations

import json
import time
from typing import Any

from gw2_progression.expert_ai.celery_app import process_expert_ai_task
from gw2_progression.expert_ai.core import ExpertAISystem


def run_once() -> dict:
    system = ExpertAISystem()
    return {"status": "ready", "persistence": system.persistence.health(), "feedback": system.feedback.status()}


def consume_once(system: ExpertAISystem | None = None, count: int = 1) -> dict[str, Any]:
    system = system or ExpertAISystem()
    tasks = system.persistence.dequeue_tasks(count=count)
    results = []
    for task in tasks:
        result = process_expert_ai_task(task["payload"])
        ack = system.persistence.ack_task(task["id"])
        results.append({"id": task["id"], "result": result, "ack": ack})
    return {"consumed": len(tasks), "results": results}


def main() -> None:
    while True:
        heartbeat = run_once()
        consumed = consume_once()
        print(json.dumps({"heartbeat": heartbeat, "queue": consumed}, sort_keys=True), flush=True)
        time.sleep(60)


if __name__ == "__main__":
    main()
