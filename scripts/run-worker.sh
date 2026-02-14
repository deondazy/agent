#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -d ".venv" ]; then
  echo "Missing virtualenv at $ROOT_DIR/.venv. Run ./scripts/install.sh first." >&2
  exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate

exec .venv/bin/celery -A denosysbot.queue.celery_app worker --loglevel=INFO
