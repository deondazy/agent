"""Data contracts used by orchestration stages."""

from dataclasses import dataclass, field

from denosysbot.domain.states import RunState


@dataclass(slots=True)
class RunContext:
    run_id: str
    issue_ref: str
    repo_target: str
    state: RunState = RunState.QUEUED
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class StageResult:
    run_id: str
    stage: RunState
    next_state: RunState
    status: str
    summary: str
