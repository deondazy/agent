from openclaw_agent.domain.states import RunState
from openclaw_agent.orchestration.engine import OrchestrationEngine


def test_engine_returns_next_stage_for_new_run() -> None:
    stage = OrchestrationEngine().next_stage("queued")
    assert stage == RunState.INGESTING
