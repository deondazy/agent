"""Celery application instance."""

try:
    from celery import Celery
except ModuleNotFoundError:  # pragma: no cover - exercised in dependency-light environments
    class _DummyConfig(dict):
        def update(self, *args, **kwargs) -> None:
            super().update(*args, **kwargs)

    class Celery:  # type: ignore[override]
        def __init__(self, *args, **kwargs):
            self.conf = _DummyConfig()

from openclaw_agent.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "openclaw_agent",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    timezone="UTC",
)
