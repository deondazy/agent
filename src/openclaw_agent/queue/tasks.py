"""Queue tasks for staged run execution."""

try:
    from celery import shared_task
except ModuleNotFoundError:  # pragma: no cover - exercised in dependency-light environments
    def shared_task(*decorator_args, **decorator_kwargs):  # type: ignore[misc]
        def _decorate(func):
            return func

        if decorator_args and callable(decorator_args[0]) and not decorator_kwargs:
            return decorator_args[0]
        return _decorate

from openclaw_agent.domain.states import parse_state


@shared_task(name="openclaw.dispatch_stage")
def dispatch_stage(run_id: str, stage: str) -> dict[str, str]:
    parsed_stage = parse_state(stage)
    return {
        "run_id": run_id,
        "stage": parsed_stage.value,
        "status": "queued",
    }
