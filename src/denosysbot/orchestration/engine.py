"""Run stage progression helpers."""

from denosysbot.domain.states import RunState, next_stage, parse_state
from denosysbot.orchestration.contracts import RunContext, StageResult


class OrchestrationEngine:
    """Minimal stage orchestrator used by API and worker tasks."""

    def next_stage(self, current: str | RunState) -> RunState:
        return next_stage(current)

    def run_stage(self, context: RunContext, stage: str | RunState) -> StageResult:
        active_stage = parse_state(stage)
        upcoming_state = next_stage(active_stage)
        return StageResult(
            run_id=context.run_id,
            stage=active_stage,
            next_state=upcoming_state,
            status="queued",
            summary=f"{active_stage.value} completed",
        )
