# DenosysBot (Scaffold)

This repository contains a Python modular-monolith scaffold for a DenosysBot-style autonomous coding system.

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
cd /path/to/agent
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
.venv/bin/uvicorn denosysbot.main:app --reload --app-dir "$(pwd)"
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
4. Launches a Textual-based interactive walkthrough to write/update `.env`, querying each selected provider for live available models before prompting model selection
5. Prints exact commands to start API, Redis, and Celery worker

You can also run the walkthrough directly after install:

```bash
denosysbot-installer --env-file .env
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
DENOSYSBOT_REPO_URL="https://github.com/deondazy/agent.git" \
DENOSYSBOT_REF="main" \
DENOSYSBOT_INSTALL_DIR="$HOME/agent" \
curl -fsSL https://raw.githubusercontent.com/deondazy/agent/main/scripts/bootstrap-install.sh | bash
```

## Run tests

```bash
cd /path/to/agent
source .venv/bin/activate
pytest -q
```

## Start a worker

```bash
cd /path/to/agent
source .venv/bin/activate
.venv/bin/celery -A denosysbot.queue.celery_app worker --loglevel=INFO
```

Or use helper scripts:

```bash
./scripts/run-api.sh
./scripts/run-worker.sh
```

## Chat TUI

After install, open the Textual chat session:

```bash
cd /path/to/agent
source .venv/bin/activate
denosysbot tui
```

Commands inside TUI:

- `/help` show commands
- `/reset` clear conversation context
- `/exit` quit

## Model providers

Configure keys with environment variables:

- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `GEMINI_API_KEY`
- `OLLAMA_API_KEY` (optional for local Ollama)

Provider gateway runtime configuration:

- `DENOSYSBOT_MODEL_FALLBACK_ORDER` (comma-separated, e.g. `openai,anthropic,gemini,ollama`)
- `DENOSYSBOT_MODEL_OPENAI_MODEL`, `DENOSYSBOT_MODEL_OPENAI_BASE_URL`
- `DENOSYSBOT_MODEL_OPENAI_TIMEOUT_SECONDS`, `DENOSYSBOT_MODEL_OPENAI_MAX_RETRIES`
- `DENOSYSBOT_MODEL_OPENAI_INITIAL_BACKOFF_SECONDS`, `DENOSYSBOT_MODEL_OPENAI_MAX_BACKOFF_SECONDS`
- `DENOSYSBOT_MODEL_ANTHROPIC_MODEL`, `DENOSYSBOT_MODEL_ANTHROPIC_BASE_URL`
- `DENOSYSBOT_MODEL_ANTHROPIC_VERSION`, `DENOSYSBOT_MODEL_ANTHROPIC_TIMEOUT_SECONDS`
- `DENOSYSBOT_MODEL_ANTHROPIC_MAX_RETRIES`
- `DENOSYSBOT_MODEL_ANTHROPIC_INITIAL_BACKOFF_SECONDS`, `DENOSYSBOT_MODEL_ANTHROPIC_MAX_BACKOFF_SECONDS`
- `DENOSYSBOT_MODEL_GEMINI_MODEL`, `DENOSYSBOT_MODEL_GEMINI_BASE_URL`
- `DENOSYSBOT_MODEL_GEMINI_TIMEOUT_SECONDS`, `DENOSYSBOT_MODEL_GEMINI_MAX_RETRIES`
- `DENOSYSBOT_MODEL_GEMINI_INITIAL_BACKOFF_SECONDS`, `DENOSYSBOT_MODEL_GEMINI_MAX_BACKOFF_SECONDS`
- `DENOSYSBOT_MODEL_OLLAMA_MODEL`, `DENOSYSBOT_MODEL_OLLAMA_BASE_URL`
- `DENOSYSBOT_MODEL_OLLAMA_TIMEOUT_SECONDS`, `DENOSYSBOT_MODEL_OLLAMA_MAX_RETRIES`
- `DENOSYSBOT_MODEL_OLLAMA_INITIAL_BACKOFF_SECONDS`, `DENOSYSBOT_MODEL_OLLAMA_MAX_BACKOFF_SECONDS`

Provider adapters implemented:

- `OpenAIProvider` -> `POST /v1/responses`
- `AnthropicProvider` -> `POST /v1/messages`
- `GeminiProvider` -> `POST /v1beta/models/{model}:generateContent`
- `OllamaProvider` -> `POST /api/generate`

Each adapter includes retry/backoff for transient HTTP failures and raises `ProviderError` for non-retriable failures. `ModelGateway` handles cross-provider fallback.
`FastAPI` startup now builds and stores the gateway at `app.state.model_gateway`.

## FastAPI dependency access

Use `denosysbot.api.dependencies.get_model_gateway` when routes/services need model access through dependency injection:

```python
from fastapi import Depends
from denosysbot.adapters.models.gateway import ModelGateway
from denosysbot.api.dependencies import get_model_gateway

def route_handler(gateway: ModelGateway = Depends(get_model_gateway)):
    ...
```

If startup wiring is missing, the dependency returns HTTP `500` with `model_gateway_unavailable`.

## Notes

This is still a v1 scaffold. Model API calls are implemented; VM provider APIs and persistent database storage remain interface-level placeholders.
