#!/usr/bin/env bash
# MOAB web — local board editor over board.md (LAN-accessible, no auth).
# Usage:  ./run.sh [PORT]     (default 8770; binds 0.0.0.0)

set -euo pipefail

cd "$(dirname "$0")"
PORT="${1:-8770}"
VENV=".venv"

if [ ! -d "$VENV" ]; then
  echo "[moab-web] creating venv + installing fastapi/uvicorn (uv)…"
  if command -v uv >/dev/null 2>&1; then
    uv venv "$VENV"
    "$VENV/bin/python" -m ensurepip -q 2>/dev/null || true
    uv pip install --python "$VENV/bin/python" -q fastapi "uvicorn[standard]"
  else
    python3 -m venv "$VENV"
    "$VENV/bin/pip" install -q --upgrade pip fastapi "uvicorn[standard]"
  fi
fi

echo "[moab-web] http://0.0.0.0:${PORT}  (LAN — no auth)"
exec "$VENV/bin/python" -m uvicorn app:app --host 0.0.0.0 --port "$PORT"
