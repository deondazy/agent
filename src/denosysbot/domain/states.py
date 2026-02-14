"""Run lifecycle states and transition helpers."""

from enum import Enum


class RunState(str, Enum):
    QUEUED = "queued"
    INGESTING = "ingesting"
    PLANNING = "planning"
    PROVISIONING_VM = "provisioning_vm"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    INTEGRATING = "integrating"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


VALID_TRANSITIONS: dict[RunState, set[RunState]] = {
    RunState.QUEUED: {RunState.INGESTING, RunState.CANCELED},
    RunState.INGESTING: {RunState.PLANNING, RunState.FAILED, RunState.CANCELED},
    RunState.PLANNING: {RunState.PROVISIONING_VM, RunState.FAILED, RunState.CANCELED},
    RunState.PROVISIONING_VM: {RunState.EXECUTING, RunState.FAILED, RunState.CANCELED},
    RunState.EXECUTING: {RunState.VERIFYING, RunState.FAILED, RunState.CANCELED},
    RunState.VERIFYING: {RunState.INTEGRATING, RunState.FAILED, RunState.CANCELED},
    RunState.INTEGRATING: {RunState.SUCCEEDED, RunState.FAILED, RunState.CANCELED},
    RunState.SUCCEEDED: set(),
    RunState.FAILED: set(),
    RunState.CANCELED: set(),
}


class StateTransitionError(ValueError):
    """Raised when a state transition is invalid."""


def parse_state(value: str | RunState) -> RunState:
    if isinstance(value, RunState):
        return value
    return RunState(value)


def can_transition(current: str | RunState, nxt: str | RunState) -> bool:
    current_state = parse_state(current)
    next_state = parse_state(nxt)
    return next_state in VALID_TRANSITIONS[current_state]


def assert_transition(current: str | RunState, nxt: str | RunState) -> RunState:
    if not can_transition(current, nxt):
        raise StateTransitionError(f"invalid transition: {current} -> {nxt}")
    return parse_state(nxt)


def next_stage(current: str | RunState) -> RunState:
    stage_map = {
        RunState.QUEUED: RunState.INGESTING,
        RunState.INGESTING: RunState.PLANNING,
        RunState.PLANNING: RunState.PROVISIONING_VM,
        RunState.PROVISIONING_VM: RunState.EXECUTING,
        RunState.EXECUTING: RunState.VERIFYING,
        RunState.VERIFYING: RunState.INTEGRATING,
        RunState.INTEGRATING: RunState.SUCCEEDED,
    }
    current_state = parse_state(current)
    if current_state not in stage_map:
        raise StateTransitionError(f"run is terminal: {current_state.value}")
    return stage_map[current_state]
