#!/usr/bin/env bash
set -euo pipefail

HA_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
REPO_DIR="$(dirname "$(dirname "$HA_DIR")")"

PYTHON="${REPO_DIR}/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
    PYTHON="$(command -v python3)"
fi

exec "$PYTHON" "${HA_DIR}/wrapper.py" "$@"