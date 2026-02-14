#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

choose_python() {
  if command -v python3.12 >/dev/null 2>&1; then
    echo "python3.12"
    return
  fi
  if command -v python3 >/dev/null 2>&1; then
    echo "python3"
    return
  fi
  echo "python"
}

PYTHON_BIN="$(choose_python)"

echo "Using Python: $PYTHON_BIN"

if [ ! -d ".venv" ]; then
  "$PYTHON_BIN" -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

# Some machines have pip configured with global.user=true, which breaks venv installs.
PIP_USER=0 python -m pip install --upgrade pip
PIP_USER=0 python -m pip install -e ".[dev]"

echo
echo "Starting interactive walkthrough..."
python -m openclaw_agent.installer --env-file .env

echo
echo "Install complete."
echo "Activate env: source .venv/bin/activate"
echo "Run API:      uvicorn openclaw_agent.main:app --reload"
