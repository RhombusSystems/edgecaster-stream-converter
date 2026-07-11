#!/usr/bin/env bash
set -euo pipefail

# Backend: venv + runtime deps + dev tools (pytest/ruff, per pyproject [dev]).
# Prefer 3.11-3.13: the pinned pydantic has no prebuilt wheels for newer Pythons.
PYTHON=python3
for candidate in python3.12 python3.13 python3.11; do
  if command -v "$candidate" >/dev/null 2>&1; then PYTHON=$candidate; break; fi
done
"$PYTHON" -m venv venv
venv/bin/pip install --upgrade pip
venv/bin/pip install -r requirements.txt
venv/bin/pip install pytest pytest-asyncio ruff

# Frontend deps
(cd frontend && npm install)

# Carry over local dev config/state (API key, enabled cameras) from the root
# checkout so streams work in this workspace too. backend/data is gitignored.
if [ -n "${SUPERSET_ROOT_PATH:-}" ] && [ -d "$SUPERSET_ROOT_PATH/backend/data" ]; then
  mkdir -p backend/data
  cp -R "$SUPERSET_ROOT_PATH/backend/data/." backend/data/
fi
