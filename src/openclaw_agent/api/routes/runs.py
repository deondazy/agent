"""Run lifecycle routes."""

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from openclaw_agent.adapters.models.gateway import ModelGateway
from openclaw_agent.api.dependencies import get_model_gateway
from openclaw_agent.api.schemas import CreateRunRequest, RunListResponse, RunResponse
from openclaw_agent.domain.states import RunState
from openclaw_agent.orchestration.engine import OrchestrationEngine

router = APIRouter(prefix="/runs", tags=["runs"])
_engine = OrchestrationEngine()

_RUNS: dict[str, RunResponse] = {}


def clear_run_store() -> None:
    _RUNS.clear()


@router.post("", response_model=RunResponse, status_code=201)
def create_run(
    payload: CreateRunRequest,
    _model_gateway: ModelGateway = Depends(get_model_gateway),
) -> RunResponse:
    run_id = str(uuid4())
    response = RunResponse(
        run_id=run_id,
        state=RunState.QUEUED.value,
        issue_ref=payload.issue_ref,
        repo_target=payload.repo_target,
    )
    _RUNS[run_id] = response
    return response


@router.get("", response_model=RunListResponse)
def list_runs() -> RunListResponse:
    return RunListResponse(runs=list(_RUNS.values()))


@router.get("/{run_id}", response_model=RunResponse)
def get_run(run_id: str) -> RunResponse:
    run = _RUNS.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run_not_found")
    return run


@router.post("/{run_id}/advance", response_model=RunResponse)
def advance_run(run_id: str) -> RunResponse:
    run = _RUNS.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run_not_found")

    next_state = _engine.next_stage(run.state)
    updated = RunResponse(
        run_id=run.run_id,
        state=next_state.value,
        issue_ref=run.issue_ref,
        repo_target=run.repo_target,
    )
    _RUNS[run_id] = updated
    return updated
