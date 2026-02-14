# OpenClaw-Style Agent Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a working v1 scaffold for an OpenClaw-style autonomous coding agent with issue-to-PR orchestration primitives.

**Architecture:** Implement a Python modular monolith with strict module boundaries for API, orchestration, policy, adapters, and worker execution. Start with deterministic core behavior (state machine, policy, orchestration contracts) and then layer API and worker integration. Keep external integrations adapter-based and test with fakes.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, Celery, Redis, SQLAlchemy, httpx, pytest

### Task 1: Project Bootstrap and Configuration

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `src/openclaw_agent/__init__.py`
- Create: `src/openclaw_agent/core/config.py`
- Create: `tests/test_config.py`

**Step 1: Write the failing test**

```python
from openclaw_agent.core.config import Settings


def test_defaults_are_loaded():
    settings = Settings()
    assert settings.app_name == "openclaw-agent"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py::test_defaults_are_loaded -v`
Expected: FAIL with `ModuleNotFoundError` for `openclaw_agent`

**Step 3: Write minimal implementation**

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "openclaw-agent"
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py::test_defaults_are_loaded -v`
Expected: PASS

**Step 5: Commit**

```bash
git add pyproject.toml README.md src/openclaw_agent/__init__.py src/openclaw_agent/core/config.py tests/test_config.py
git commit -m "chore: bootstrap openclaw agent project"
```

### Task 2: Run State Machine

**Files:**
- Create: `src/openclaw_agent/domain/states.py`
- Create: `tests/domain/test_states.py`

**Step 1: Write the failing test**

```python
def test_valid_transition_from_queued_to_ingesting():
    assert can_transition("queued", "ingesting")
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/domain/test_states.py::test_valid_transition_from_queued_to_ingesting -v`
Expected: FAIL with `NameError` or missing function

**Step 3: Write minimal implementation**

```python
VALID_TRANSITIONS = {"queued": {"ingesting"}}


def can_transition(current: str, nxt: str) -> bool:
    return nxt in VALID_TRANSITIONS.get(current, set())
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/domain/test_states.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/openclaw_agent/domain/states.py tests/domain/test_states.py
git commit -m "feat: add run state machine transitions"
```

### Task 3: Policy Engine for Command Classification

**Files:**
- Create: `src/openclaw_agent/policy/engine.py`
- Create: `tests/policy/test_engine.py`

**Step 1: Write the failing test**

```python
def test_rejects_disallowed_command():
    policy = PolicyEngine()
    decision = policy.evaluate_command("rm -rf /")
    assert decision.allowed is False
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/policy/test_engine.py::test_rejects_disallowed_command -v`
Expected: FAIL with import error or missing class

**Step 3: Write minimal implementation**

```python
@dataclass
class PolicyDecision:
    allowed: bool
    reason: str


class PolicyEngine:
    def evaluate_command(self, command: str) -> PolicyDecision:
        if "rm -rf /" in command:
            return PolicyDecision(False, "blocked")
        return PolicyDecision(True, "allowed")
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/policy/test_engine.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/openclaw_agent/policy/engine.py tests/policy/test_engine.py
git commit -m "feat: implement command policy engine"
```

### Task 4: Orchestration Engine Skeleton

**Files:**
- Create: `src/openclaw_agent/orchestration/engine.py`
- Create: `src/openclaw_agent/orchestration/contracts.py`
- Create: `tests/orchestration/test_engine.py`

**Step 1: Write the failing test**

```python
def test_engine_returns_next_stage_for_new_run():
    stage = OrchestrationEngine().next_stage("queued")
    assert stage == "ingesting"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/orchestration/test_engine.py::test_engine_returns_next_stage_for_new_run -v`
Expected: FAIL because engine is missing

**Step 3: Write minimal implementation**

```python
class OrchestrationEngine:
    def next_stage(self, state: str) -> str:
        mapping = {"queued": "ingesting"}
        return mapping[state]
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/orchestration/test_engine.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/openclaw_agent/orchestration/contracts.py src/openclaw_agent/orchestration/engine.py tests/orchestration/test_engine.py
git commit -m "feat: add orchestration engine skeleton"
```

### Task 5: API Endpoints for Run Lifecycle

**Files:**
- Create: `src/openclaw_agent/api/schemas.py`
- Create: `src/openclaw_agent/api/routes/runs.py`
- Create: `src/openclaw_agent/main.py`
- Create: `tests/api/test_runs.py`

**Step 1: Write the failing test**

```python
def test_create_run_returns_run_id(client):
    response = client.post("/runs", json={"title": "Fix bug"})
    assert response.status_code == 201
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/api/test_runs.py::test_create_run_returns_run_id -v`
Expected: FAIL because app/router not implemented

**Step 3: Write minimal implementation**

```python
@app.post("/runs", status_code=201)
def create_run(payload: CreateRunRequest):
    return {"run_id": "...", "state": "queued"}
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/api/test_runs.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/openclaw_agent/api/schemas.py src/openclaw_agent/api/routes/runs.py src/openclaw_agent/main.py tests/api/test_runs.py
git commit -m "feat: expose run lifecycle api"
```

### Task 6: Model Gateway with Provider Fallback

**Files:**
- Create: `src/openclaw_agent/adapters/models/base.py`
- Create: `src/openclaw_agent/adapters/models/gateway.py`
- Create: `src/openclaw_agent/adapters/models/openai.py`
- Create: `src/openclaw_agent/adapters/models/anthropic.py`
- Create: `src/openclaw_agent/adapters/models/ollama.py`
- Create: `tests/adapters/test_model_gateway.py`

**Step 1: Write the failing test**

```python
def test_gateway_falls_back_when_primary_fails():
    gateway = ModelGateway([...])
    assert gateway.generate("prompt") == "fallback-response"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/adapters/test_model_gateway.py::test_gateway_falls_back_when_primary_fails -v`
Expected: FAIL due to missing gateway behavior

**Step 3: Write minimal implementation**

```python
for provider in self.providers:
    try:
        return provider.generate(prompt)
    except ProviderError:
        continue
raise ProviderError("all providers failed")
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/adapters/test_model_gateway.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/openclaw_agent/adapters/models tests/adapters/test_model_gateway.py
git commit -m "feat: implement provider fallback gateway"
```

### Task 7: Worker Queue and Stage Tasks

**Files:**
- Create: `src/openclaw_agent/queue/celery_app.py`
- Create: `src/openclaw_agent/queue/tasks.py`
- Create: `tests/queue/test_tasks.py`

**Step 1: Write the failing test**

```python
def test_dispatch_stage_invokes_orchestration(monkeypatch):
    result = dispatch_stage("run-1", "ingesting")
    assert result["stage"] == "ingesting"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/queue/test_tasks.py::test_dispatch_stage_invokes_orchestration -v`
Expected: FAIL due to missing task function

**Step 3: Write minimal implementation**

```python
@shared_task
def dispatch_stage(run_id: str, stage: str) -> dict:
    return {"run_id": run_id, "stage": stage, "status": "queued"}
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/queue/test_tasks.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/openclaw_agent/queue/celery_app.py src/openclaw_agent/queue/tasks.py tests/queue/test_tasks.py
git commit -m "feat: add celery queue stage tasks"
```

### Task 8: VM Worker Contract and README Runbook

**Files:**
- Create: `src/openclaw_agent/vm/contracts.py`
- Create: `src/openclaw_agent/vm/provisioner.py`
- Modify: `README.md`
- Create: `tests/vm/test_provisioner.py`

**Step 1: Write the failing test**

```python
def test_provisioner_returns_worker_context():
    context = VMProvisioner().provision("run-1")
    assert context.run_id == "run-1"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/vm/test_provisioner.py::test_provisioner_returns_worker_context -v`
Expected: FAIL because provisioner is missing

**Step 3: Write minimal implementation**

```python
class VMProvisioner:
    def provision(self, run_id: str) -> WorkerContext:
        return WorkerContext(run_id=run_id, vm_id=f"vm-{run_id}")
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/vm/test_provisioner.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/openclaw_agent/vm/contracts.py src/openclaw_agent/vm/provisioner.py README.md tests/vm/test_provisioner.py
git commit -m "docs: add vm contract and local runbook"
```

### Task 9: Whole-Project Verification

**Files:**
- Modify: `README.md`

**Step 1: Run complete test suite**

Run: `pytest -q`
Expected: all tests passing

**Step 2: Run static checks**

Run: `python -m compileall src`
Expected: no syntax errors

**Step 3: Document final commands and outputs**

Add tested commands to `README.md` including API startup, worker startup, and test command.

**Step 4: Commit**

```bash
git add README.md
git commit -m "chore: document verification commands"
```
