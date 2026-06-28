"""Celery integration for Expert AI background jobs."""

from __future__ import annotations

try:
    from celery import Celery
except ImportError:  # pragma: no cover - production image installs celery
    Celery = None

from gw2_progression.expert_ai.core import ExpertAISystem


class _LocalCeleryFallback:
    def task(self, name: str):
        def decorator(func):
            func.task_name = name
            return func

        return decorator


def create_celery_app():
    system = ExpertAISystem()
    broker = system.persistence.config.redis_url or "redis://localhost:6379/0"
    if Celery is None:
        app = _LocalCeleryFallback()
    else:
        app = Celery("gw2_expert_ai", broker=broker, backend=broker)

    @app.task(name="expert_ai.process_task")
    def process_task(task: dict) -> dict:
        return process_expert_ai_task(task)

    return app


def process_expert_ai_task(task: dict) -> dict:
    system = ExpertAISystem()
    task_type = task.get("type", "feedback")
    if task_type == "feedback":
        return system.feedback.observe(task.get("payload", task))
    if task_type == "migrate":
        return system.persistence.migrate()
    if task_type == "health":
        return system.persistence.health()
    return {"status": "ignored", "task_type": task_type}


celery_app = create_celery_app()
