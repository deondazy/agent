"""API schemas for run lifecycle endpoints."""

from pydantic import BaseModel, Field


class CreateRunRequest(BaseModel):
    issue_ref: str = Field(min_length=1, examples=["acme/repo#42"])
    repo_target: str = Field(min_length=1, examples=["github:acme/repo"])
    prompt: str | None = None
    policy_profile: str = "default"


class RunResponse(BaseModel):
    run_id: str
    state: str
    issue_ref: str
    repo_target: str


class RunListResponse(BaseModel):
    runs: list[RunResponse]
