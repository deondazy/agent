import pytest

from denosysbot.domain.states import RunState, StateTransitionError, can_transition, next_stage


def test_valid_transition_from_queued_to_ingesting() -> None:
    assert can_transition("queued", "ingesting")


def test_invalid_transition_from_queued_to_succeeded() -> None:
    assert not can_transition(RunState.QUEUED, RunState.SUCCEEDED)


def test_next_stage_advances_pipeline() -> None:
    assert next_stage("planning") == RunState.PROVISIONING_VM


def test_next_stage_rejects_terminal_state() -> None:
    with pytest.raises(StateTransitionError):
        next_stage("succeeded")
