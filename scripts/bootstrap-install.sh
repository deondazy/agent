#!/usr/bin/env bash
set -euo pipefail

DEFAULT_REPO_URL="https://github.com/deondazy/agent.git"
DEFAULT_REF="main"
DEFAULT_INSTALL_DIR="$HOME/agent"

prompt() {
  local label="$1"
  local default_value="$2"
  local value

  if [ -t 0 ] && [ -r /dev/tty ]; then
    read -r -p "$label [$default_value]: " value </dev/tty
  elif [ -r /dev/tty ]; then
    read -r -p "$label [$default_value]: " value </dev/tty
  else
    # Non-interactive environments fall back to provided defaults/env vars.
    value=""
  fi

  if [ -z "${value}" ]; then
    echo "$default_value"
  else
    echo "$value"
  fi
}

require_command() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Missing required command: $cmd" >&2
    exit 1
  fi
}

choose_python() {
  if command -v python3.12 >/dev/null 2>&1; then
    echo "python3.12"
    return
  fi
  if command -v python3 >/dev/null 2>&1; then
    echo "python3"
    return
  fi
  if command -v python >/dev/null 2>&1; then
    echo "python"
    return
  fi
  echo ""
}

echo
echo "Agent Remote Installer"
echo "======================"
echo

require_command git

PYTHON_BIN="$(choose_python)"
if [ -z "$PYTHON_BIN" ]; then
  echo "Missing required command: python3.12/python3/python" >&2
  exit 1
fi

REPO_URL="${OPENCLAW_REPO_URL:-$DEFAULT_REPO_URL}"
REF_NAME="${OPENCLAW_REF:-$DEFAULT_REF}"
INSTALL_DIR="${OPENCLAW_INSTALL_DIR:-$DEFAULT_INSTALL_DIR}"

REPO_URL="$(prompt "Git repository URL" "$REPO_URL")"
REF_NAME="$(prompt "Git ref (branch/tag)" "$REF_NAME")"
INSTALL_DIR="$(prompt "Install directory" "$INSTALL_DIR")"

echo
echo "Using settings:"
echo "- Repo:     $REPO_URL"
echo "- Ref:      $REF_NAME"
echo "- Location: $INSTALL_DIR"
echo "- Python:   $PYTHON_BIN"
echo

mkdir -p "$INSTALL_DIR"

if [ -d "$INSTALL_DIR/.git" ]; then
  echo "Existing repository detected, updating..."
  git -C "$INSTALL_DIR" fetch --all --tags --prune
  git -C "$INSTALL_DIR" checkout "$REF_NAME"
  git -C "$INSTALL_DIR" pull --ff-only
else
  echo "Cloning repository..."
  if [ -n "$(find "$INSTALL_DIR" -mindepth 1 -maxdepth 1 2>/dev/null)" ]; then
    echo "Install directory is not empty and is not a git repository: $INSTALL_DIR" >&2
    echo "Please choose an empty directory or a directory containing this repo." >&2
    exit 1
  fi
  git clone "$REPO_URL" "$INSTALL_DIR"
  git -C "$INSTALL_DIR" checkout "$REF_NAME"
fi

if [ ! -f "$INSTALL_DIR/scripts/install.sh" ]; then
  echo "Expected installer script not found: $INSTALL_DIR/scripts/install.sh" >&2
  exit 1
fi

echo
echo "Launching interactive installer walkthrough..."
cd "$INSTALL_DIR"
bash ./scripts/install.sh
