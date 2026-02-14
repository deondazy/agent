# OpenClaw Agent (Scaffold)

This repository contains a Python modular-monolith scaffold for an OpenClaw-style autonomous coding system.

## What is implemented

- FastAPI run lifecycle endpoints
- Run state machine and orchestration skeleton
- Command policy engine with approval-aware decisions
- Model provider gateway with fallback behavior
- Real model-provider HTTP clients (OpenAI, Anthropic, Ollama) with retry/backoff
- Celery task scaffolding for stage dispatch
- Disposable VM contract and provisioner interface

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
uvicorn openclaw_agent.main:app --reload
```

## Installer Walkthrough

Run the guided installer from the project root:

```bash
./scripts/install.sh
```

What it does:

1. Detects Python (`python3.12` preferred, then `python3`)
2. Creates `.venv` if missing
3. Installs package + dev dependencies
4. Launches an interactive walkthrough to write/update `.env`
5. Prints exact commands to start API, Redis, and Celery worker

You can also run the walkthrough directly after install:

```bash
openclaw-installer --env-file .env
```

## Remote Install (curl + walkthrough)

On a different machine, you can run a remote bootstrap script that prompts for:

1. Git repository URL
2. Git ref (branch/tag)
3. Install directory

Then it clones/updates the repo and launches the interactive Q/A installer walkthrough.

```bash
curl -fsSL https://raw.githubusercontent.com/deondazy/agent/main/scripts/bootstrap-install.sh | bash
```

Non-interactive defaults can be prefilled:

```bash
OPENCLAW_REPO_URL="https://github.com/deondazy/agent.git" \
OPENCLAW_REF="main" \
OPENCLAW_INSTALL_DIR="$HOME/agent" \
curl -fsSL https://raw.githubusercontent.com/deondazy/agent/main/scripts/bootstrap-install.sh | bash
```

## Run tests

```bash
pytest -q
```

## Start a worker

```bash
celery -A openclaw_agent.queue.celery_app worker --loglevel=INFO
```

## Model providers

Configure keys with environment variables:

- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `OLLAMA_API_KEY` (optional for local Ollama)

Provider gateway runtime configuration:

- `OPENCLAW_MODEL_FALLBACK_ORDER` (comma-separated, e.g. `openai,anthropic,ollama`)
- `OPENCLAW_MODEL_OPENAI_MODEL`, `OPENCLAW_MODEL_OPENAI_BASE_URL`
- `OPENCLAW_MODEL_OPENAI_TIMEOUT_SECONDS`, `OPENCLAW_MODEL_OPENAI_MAX_RETRIES`
- `OPENCLAW_MODEL_OPENAI_INITIAL_BACKOFF_SECONDS`, `OPENCLAW_MODEL_OPENAI_MAX_BACKOFF_SECONDS`
- `OPENCLAW_MODEL_ANTHROPIC_MODEL`, `OPENCLAW_MODEL_ANTHROPIC_BASE_URL`
- `OPENCLAW_MODEL_ANTHROPIC_VERSION`, `OPENCLAW_MODEL_ANTHROPIC_TIMEOUT_SECONDS`
- `OPENCLAW_MODEL_ANTHROPIC_MAX_RETRIES`
- `OPENCLAW_MODEL_ANTHROPIC_INITIAL_BACKOFF_SECONDS`, `OPENCLAW_MODEL_ANTHROPIC_MAX_BACKOFF_SECONDS`
- `OPENCLAW_MODEL_OLLAMA_MODEL`, `OPENCLAW_MODEL_OLLAMA_BASE_URL`
- `OPENCLAW_MODEL_OLLAMA_TIMEOUT_SECONDS`, `OPENCLAW_MODEL_OLLAMA_MAX_RETRIES`
- `OPENCLAW_MODEL_OLLAMA_INITIAL_BACKOFF_SECONDS`, `OPENCLAW_MODEL_OLLAMA_MAX_BACKOFF_SECONDS`

Provider adapters implemented:

- `OpenAIProvider` -> `POST /v1/responses`
- `AnthropicProvider` -> `POST /v1/messages`
- `OllamaProvider` -> `POST /api/generate`

Each adapter includes retry/backoff for transient HTTP failures and raises `ProviderError` for non-retriable failures. `ModelGateway` handles cross-provider fallback.
`FastAPI` startup now builds and stores the gateway at `app.state.model_gateway`.

## FastAPI dependency access

Use `openclaw_agent.api.dependencies.get_model_gateway` when routes/services need model access through dependency injection:

```python
from fastapi import Depends
from openclaw_agent.adapters.models.gateway import ModelGateway
from openclaw_agent.api.dependencies import get_model_gateway

def route_handler(gateway: ModelGateway = Depends(get_model_gateway)):
    ...
```

If startup wiring is missing, the dependency returns HTTP `500` with `model_gateway_unavailable`.

## Notes

This is still a v1 scaffold. Model API calls are implemented; VM provider APIs and persistent database storage remain interface-level placeholders.
