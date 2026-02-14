# OpenClaw-Style Agent Design

**Date:** February 14, 2026
**Status:** Approved

## Goal
Build a Clawdbot-like autonomous coding system that turns GitHub issues into pull requests with high autonomy, multi-provider model support, and auditable execution.

## Scope Choices Confirmed
- Runtime stack: Python + FastAPI + Celery/Redis
- Autonomy level: full autonomy
- Targets: local workspaces and GitHub repositories
- Model providers: OpenAI, Anthropic, Ollama (fallback capable)
- Primary workflow: issue -> branch -> code -> tests -> PR
- Privilege model: root inside disposable VM workers only
- Deployment model: single-tenant self-hosted service
- Architecture style: modular monolith

## Core Architecture
The system is delivered as a single deployable service with strict internal module boundaries.

### Modules
- API layer (FastAPI): run creation, status, timeline, artifacts, webhooks
- Orchestration: run graph/state machine and stage scheduling
- Queue and workers (Celery + Redis): idempotent stage jobs with retries
- Policy engine: command/action classification and execution gates
- Repo adapters: local and GitHub repository implementations
- Model gateway: provider-agnostic model interface with adapter fallback
- VM execution: disposable worker provisioning and teardown
- Storage: Postgres metadata + artifact store for logs/diffs/reports
- Observability: structured logs, per-run timeline, audit trail

## End-to-End Flow
1. Ingest issue context (title/body/comments/labels/repo metadata)
2. Generate execution plan (files, commands, verification intent)
3. Provision disposable VM worker and inject short-lived credentials
4. Execute iterative edits and commands
5. Verify required checks and issue-specific acceptance criteria
6. Integrate: branch, commit, push, PR create/update
7. Teardown VM, revoke credentials, finalize artifacts

## Data Model and State
### Core tables
- `runs`: lifecycle, target, provider config, branch/PR metadata
- `stage_attempts`: stage input/output hashes and attempt history
- `commands`: full execution transcript and exit metadata
- `artifacts`: patches, logs, reports, summaries
- `provider_events`: model requests, token usage, retries, latency
- `integration_events`: GitHub calls and webhook idempotency events

### State machine
`queued -> ingesting -> planning -> provisioning_vm -> executing -> verifying -> integrating -> succeeded|failed|canceled`

State transitions are append-only and validated by transition rules.

## Reliability and Recovery
- Stage-level idempotency with resumable checkpoints
- Transient failure retries with bounded backoff
- Provider fallback order for model failures
- Conflict handling via rebase + reverify subflow
- Terminal summaries always produced with actionable error reasons

## Security and Containment
Unsafe host-level root is rejected.

Chosen model:
- Agent runs as root only inside ephemeral disposable VMs
- VM is destroyed after each run
- Credentials are short-lived and scoped to run/repo
- Audit logs are immutable and replayable

## Verification Strategy
1. Unit/contract tests for planner schema, policy decisions, adapters
2. Integration tests for execution loop, retries, repo operations
3. End-to-end tests for full issue -> PR pipeline in a composed environment

## Delivery Slices
- Slice A: local repo + one provider + VM execution + timeline
- Slice B: GitHub ingestion/integration and PR lifecycle
- Slice C: multi-provider gateway with fallback and retry policy
- Slice D: production hardening (quotas, retention, alerts, admin controls)

## Operational Readiness Gates
- Deterministic replay from artifacts
- No unbounded retry loops
- Guaranteed VM teardown on all failure paths
- Reconciliation job for partially integrated branch/PR state
